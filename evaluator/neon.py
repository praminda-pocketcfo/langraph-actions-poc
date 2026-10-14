"""Update evaluation_runs rows owned by the portal."""

from __future__ import annotations

import json
import os
from typing import Any


def _connect():
    import psycopg

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to update evaluation rows")
    return psycopg.connect(database_url)


def mark_running(evaluation_id: str, *, head_sha: str | None = None, run_url: str | None = None) -> None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE evaluation_runs
                SET status = 'running',
                    head_sha = COALESCE(%s, head_sha),
                    github_run_url = COALESCE(%s, github_run_url),
                    updated_at = NOW()
                WHERE id = %s::uuid
                """,
                (head_sha, run_url, evaluation_id),
            )
            if cur.rowcount != 1:
                raise RuntimeError(f"evaluation_runs row not found for id={evaluation_id}")
        conn.commit()


def mark_error(evaluation_id: str, message: str, *, run_url: str | None = None) -> None:
    result = {"version": 1, "evaluation_id": evaluation_id, "status": "error", "error": message}
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE evaluation_runs
                SET status = 'error',
                    result = %s::jsonb,
                    github_run_url = COALESCE(%s, github_run_url),
                    updated_at = NOW()
                WHERE id = %s::uuid
                """,
                (json.dumps(result), run_url, evaluation_id),
            )
            if cur.rowcount != 1:
                raise RuntimeError(f"evaluation_runs row not found for id={evaluation_id}")
        conn.commit()


def publish_result(
    evaluation_id: str,
    *,
    result: dict[str, Any],
    state: dict[str, Any],
    recommendation: str | None,
    head_sha: str | None = None,
    run_url: str | None = None,
) -> None:
    status = result.get("status") or "awaiting_panel"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE evaluation_runs
                SET status = %s,
                    recommendation = %s,
                    result = %s::jsonb,
                    state = %s::jsonb,
                    head_sha = COALESCE(%s, head_sha),
                    github_run_url = COALESCE(%s, github_run_url),
                    updated_at = NOW()
                WHERE id = %s::uuid
                """,
                (
                    status,
                    recommendation,
                    json.dumps(result),
                    json.dumps(state),
                    head_sha,
                    run_url,
                    evaluation_id,
                ),
            )
            if cur.rowcount != 1:
                raise RuntimeError(f"evaluation_runs row not found for id={evaluation_id}")
        conn.commit()


def fetch_result(evaluation_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT result FROM evaluation_runs WHERE id = %s::uuid",
                (evaluation_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            value = row[0]
            if isinstance(value, str):
                return json.loads(value)
            return value
