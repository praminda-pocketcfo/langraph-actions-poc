-- Apply once to the Neon database used by the academy portal.
-- Portal inserts pending rows; this repo's Actions job updates by id.

CREATE TABLE IF NOT EXISTS evaluation_runs (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  portal_user_id  TEXT NOT NULL,
  course_id       TEXT NOT NULL,
  project_id      TEXT NOT NULL,
  submission_repo TEXT NOT NULL,
  pr_number       INTEGER NOT NULL,
  head_sha        TEXT,
  status          TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'running', 'awaiting_panel', 'error')),
  recommendation  TEXT CHECK (recommendation IN ('pass', 'borderline', 'fail')),
  result          JSONB,
  state           JSONB,
  github_run_url  TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS evaluation_runs_portal_user_idx
  ON evaluation_runs (portal_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS evaluation_runs_pr_idx
  ON evaluation_runs (submission_repo, pr_number, created_at DESC);
