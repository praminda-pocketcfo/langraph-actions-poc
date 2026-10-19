# Submission portal

Small TanStack Start app. A learner uploads a project zip. The server writes those files to a private GitHub repository the learner is not a member of, opens a draft pull request, and dispatches `project-evaluation.yml`.

GitHub cannot hide a branch from someone who can read the repo, and a Team seat is billed when that person is invited. This app does not invite learners. Two landing modes are on the form:

- **Branch** in one existing private repo (`GITHUB_SUBMISSION_REPO`). Zero seats. A later collaborator can read every submission.
- **New private repo** per upload. Still zero seats, and a later grant covers only that repo. The token must be a classic PAT or a GitHub App, because a fine-grained token does not see repositories created after it was issued.

The grader needs a pull request number. A branch by itself is not an input the current workflow accepts.

## Run locally

```bash
cd portal
npm install
cp .env.example .env
npm run dev
```

Open http://localhost:3000. `npm run check` runs the zip-filter tests. `npm run build` is the Vercel build.

## Environment

See `.env.example`. On Vercel, set the project **Root Directory** to `portal` and add the same variables. The server refuses to write if the destination repository is public.

The evaluation repository still needs `SUBMISSION_TOKEN` when the submission lives in a different repo (contents read, pull requests write). In new-repo mode that token has to see newly created repositories, or the workflow cannot fetch files.

## Limits

Zip uploads are capped at 4 MB so they fit a Vercel function body. `.git`, `node_modules`, virtualenvs, and `.env` files are not committed. There is no sign-in and no Neon insert in this POC. The evaluation id is generated here and passed through to the workflow.
