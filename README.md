# Learner evaluation POC

Private evaluation repo for a leaner certification flow. The academy **portal** owns learner identity. For this POC, dispatch this repo with an `evaluation_id` and PR details; Actions runs instructor unit tests and a LangGraph rubric graph, then posts the result as a PR comment. Neon writes are **off by default** (`--write-neon` later) so you can run without a database.

A GitHub webhook is **not** used to start evaluation. Actions never invents who the learner is.

## What you need (external dependencies)


| Dependency                       | Purpose                                                 | Required for                  |
| -------------------------------- | ------------------------------------------------------- | ----------------------------- |
| **Python 3.11+**                 | Run packs, pytest, and `python -m evaluator`            | Local + CI                    |
| **OpenAI API**                   | Specialist, verifier, and feedback model calls          | Live evaluation (not dry-run) |
| **Neon (Postgres)**              | Optional `evaluation_runs` table (opt-in via `--write-neon`) | Later portal path only |
| **GitHub**                       | Submission PR, `workflow_dispatch`, optional PR comment | CI / live PR path             |
| **Vercel portal** (existing app) | Authenticated submit + read result by evaluation id     | Production; not in this repo  |


Local **dry-run** needs only Python. No OpenAI key, Neon, or GitHub token.

## Repository layout

```
packs/<project_id>/     # Instructor pack: manifest, rubric, tests
fixtures/               # Sample submissions for local dry-run
evaluator/              # LangGraph graph + Neon/GitHub publishers
tests/                  # Unit tests for scoring, routing, dry-run graph
db/evaluation_runs.sql  # Neon schema (apply once)
.github/workflows/      # CI dry-run + workflow_dispatch grader
```

Sample pack: `word_counter` — learner submits `word_counter.py` with `count_words(text: str) -> int`.

## Neon schema (apply once)

Run against your Neon database (SQL editor or `psql "$DATABASE_URL" -f db/evaluation_runs.sql`)

**Portal writes on insert:** `id`, `portal_user_id`, `course_id`, `project_id`, `submission_repo`, `pr_number`, optional `head_sha`, `status = pending`.

**Actions updates by** `id` **only:** `status`, `recommendation`, `result`, `state`, `github_run_url`, `head_sha`. It never sets `portal_user_id` / `course_id` / `project_id`.

Portal read for a signed-in user:

```sql
SELECT * FROM evaluation_runs
WHERE id = $1 AND portal_user_id = $2;
```



## Configuration



### Environment variables / secrets


| Name               | Where                              | Used for                                                                 |
| ------------------ | ---------------------------------- | ------------------------------------------------------------------------ |
| `OPENAI_API_KEY`   | Local env or GitHub Actions secret | Live model calls                                                         |
| `EVAL_MODEL`       | Optional (default `gpt-4o-mini`)   | Model id for `init_chat_model`                                           |
| `EVAL_DRY_RUN`     | Optional (`1` / `true`)            | Force fake model; skip Neon/GitHub writes when combined with `--dry-run` |
| `DATABASE_URL`     | Local env or Actions secret        | Neon pooled connection string                                            |
| `GITHUB_TOKEN`     | Actions (automatic) or local PAT   | Read PR files; upsert evaluation comment                                 |
| `SUBMISSION_TOKEN` | Optional Actions secret            | Fine-grained PAT when the submission repo is **not** this repo           |
| `GITHUB_WORKSPACE` | Actions (automatic)                | Repo root for pack loading                                               |




### GitHub repository secrets (this repo)

Add under **Settings → Secrets and variables → Actions**:

1. `OPENAI_API_KEY` (required for live evaluation unless dry-run is on)

**Actions variable** (Settings → Secrets and variables → Actions → **Variables**):

- `EVAL_DRY_RUN` — set to `true` / `1` / `yes` to inject `--dry-run` (fake model, no API key). Leave unset or `false` for live evaluation.

Optional secrets:

- `SUBMISSION_TOKEN` — if comments/files are on a different submission repository
- `DATABASE_URL` — only when you turn Neon writes back on with `--write-neon`

Note: `EVAL_DRY_RUN` / `--dry-run` uses the fake model (no API key). It still posts the PR comment. Neon stays off unless `--write-neon`.

### Portal (Vercel) secrets — not in this repo

When the authenticated submit route exists:

- Token that can `workflow_dispatch` this repo’s `project-evaluation.yml`
- Same Neon `DATABASE_URL` (or app connection) the portal already uses



## Run locally



### 1. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```



### 2. Unit tests + dry-run graph (no external services)

```bash
EVAL_DRY_RUN=1 python -m pytest -q
```

`pytest.ini` limits collection to [`tests/`](tests/) (evaluator unit tests). It does **not** run [`packs/*/tests`](packs/word_counter/tests) — those need a submission file under `packs/<project>/submission/` (created by the Actions workflow, or by copying the fixture below).

### 3. Dry-run the evaluator CLI on the fixture

Instructor pack tests expect `packs/word_counter/submission/word_counter.py`. Copy the fixture first, then generate JUnit and run the graph:

```bash
mkdir -p packs/word_counter/submission
cp fixtures/word_counter_partial/word_counter.py packs/word_counter/submission/word_counter.py
python -m pytest packs/word_counter/tests -q --junitxml=/tmp/wc-junit.xml

python -m evaluator \
  --evaluation-id 00000000-0000-4000-8000-000000000001 \
  --project-id word_counter \
  --submission-dir fixtures/word_counter_partial \
  --junit /tmp/wc-junit.xml \
  --dry-run

rm -rf packs/word_counter/submission
```

`--dry-run` uses a deterministic fake model and does **not** write to Neon or GitHub. Prints the result JSON (status `awaiting_panel`).

### 4. Live local run (OpenAI + Neon + optional GitHub)

```bash
export OPENAI_API_KEY=sk-...
export DATABASE_URL='postgresql://...@.../neondb?sslmode=require'
# Optional: export GITHUB_TOKEN=ghp_...  # to fetch a real PR and comment

# Portal (or you) must insert the row first, e.g.:
# INSERT INTO evaluation_runs (id, portal_user_id, course_id, project_id, submission_repo, pr_number, status)
# VALUES ('...', 'user-1', 'course-1', 'word_counter', 'owner/repo', 12, 'pending');

python -m evaluator \
  --evaluation-id <uuid-from-insert> \
  --project-id word_counter \
  --submission-repo owner/repo \
  --pr-number 12 \
  --junit /tmp/wc-junit.xml
```

Live or dry-run both upsert a PR comment containing `<!-- learner-evaluation:v1 -->` (unless `--skip-github`). Neon is skipped unless you also pass `--write-neon` (requires `DATABASE_URL`).

## Run in GitHub Actions / CI

Workflows live under [`.github/workflows/`](.github/workflows/):

| Workflow | Trigger | Purpose |
| --- | --- | --- |
| [`ci.yml`](.github/workflows/ci.yml) | Push to `main` | Install deps, `EVAL_DRY_RUN=1 pytest` — no secrets |
| [`project-evaluation.yml`](.github/workflows/project-evaluation.yml) | `workflow_dispatch` only | Grade a submission: pytest (no secrets) → LangGraph evaluate (secrets) |

There is **no** `pull_request` / `pull_request_target` grader. Learner PRs do not start evaluation by themselves.

### Dispatch inputs


| Input             | Required | Description                   |
| ----------------- | -------- | ----------------------------- |
| `evaluation_id`   | yes      | Correlation id (kept for portal/Neon later; echoed in the result JSON) |
| `submission_url` | yes      | Drive file link, `https://drive.google.com/file/d/FILE_ID/view` |
| `project_id`     | yes      | Pack id, e.g. `word_counter`  |




### Manual dispatch (stand-in for the portal)

The portal in [`portal/`](portal/) uploads the zip with the Drive client and dispatches this workflow with the file link (`https://drive.google.com/file/d/FILE_ID/view`).

```bash
gh workflow run project-evaluation.yml \
  -f evaluation_id="$(uuidgen | tr '[:upper:]' '[:lower:]')" \
  -f submission_url='https://drive.google.com/file/d/FILE_ID/view' \
  -f project_id=word_counter
```

The run downloads that zip through the Drive API, extracts it, and runs the instructor tests.



### What the evaluation workflow does

1. **Test job** — checkout this repo at `main`; download the zip from `submission_url`; extract it; stage the pack's `submission_paths`; run instructor pytest with secrets unset; upload JUnit and the extracted tree. Test failures do not skip the graph.
2. **Evaluate job** — load packs from `main`; read the extracted files from the test job's artifact; call `python -m evaluator`. It does not contact a submission repository. Neon is not written unless `--write-neon` is enabled later.

Concurrency is grouped by `evaluation_id` (cancel in progress).

### Portal submit contract (later, in Vercel)

The portal in [`portal/`](portal/) accepts the zip, stores it on Google Drive at `<learner id>/<project id>/`, and dispatches this workflow with the file link. Neon insert is not part of this POC.

## Result shape

Stored in `evaluation_runs.result` when Neon writes are turned on:

- `version`, `evaluation_id`, `pr`, `project_id`, `head_sha`, `run_url`
- `test`: `{ passed, failed, errors }`
- `criteria[]`: `id`, `area`, `level`, `points`, `max`, `evidence`
- `total`, `max`, `recommendation` (`pass` | `borderline` | `fail`)
- `status` (POC ends at `awaiting_panel`)
- `feedback_markdown`

Recommendation thresholds (from the pack rubric): pass ≥ 70, borderline ≥ 50, else fail. The graph does **not** certify the learner; panel review decides.

## Out of scope for this POC

- Auto-rerun on new pushes
- Resuming the LangGraph interrupt after panel decision
- GitHub App

