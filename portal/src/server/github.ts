import { HttpError } from "./http-error";

export type PortalConfig = {
  token: string;
  evalRepo: string;
  evalWorkflow: string;
  evalRef: string;
};

export function readConfig(): PortalConfig {
  const token = process.env.GITHUB_TOKEN?.trim() ?? "";
  if (!token) {
    throw new HttpError(500, "GITHUB_TOKEN is not set on the server.");
  }
  const evalRepo = requiredRepo("GITHUB_EVAL_REPO", process.env.GITHUB_EVAL_REPO);
  return {
    token,
    evalRepo,
    evalWorkflow: process.env.GITHUB_EVAL_WORKFLOW?.trim() || "project-evaluation.yml",
    evalRef: process.env.GITHUB_EVAL_REF?.trim() || "main",
  };
}

export async function dispatchEvaluation(input: {
  config: PortalConfig;
  evaluationId: string;
  projectId: string;
  submissionUrl: string;
}): Promise<void> {
  const repo = parseRepo(input.config.evalRepo);
  const workflow = encodeURIComponent(input.config.evalWorkflow);
  console.log("submissionUrl", input.submissionUrl);
  await github(
    input.config.token,
    "POST",
    `/repos/${repo.owner}/${repo.repo}/actions/workflows/${workflow}/dispatches`,
    {
      ref: input.config.evalRef,
      inputs: {
        evaluation_id: input.evaluationId,
        project_id: input.projectId,
        submission_url: input.submissionUrl,
      },
    },
  );
}

async function github(token: string, method: string, path: string, body?: unknown): Promise<void> {
  const response = await fetch(`https://api.github.com${path}`, {
    method,
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "learner-evaluation-portal",
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(30_000),
  });
  if (response.ok) return;
  let detail = response.statusText;
  try {
    const payload = (await response.json()) as { message?: string };
    detail = payload.message ?? detail;
  } catch {
    // GitHub sometimes returns an empty error body.
  }
  if (response.status === 401 || response.status === 403) {
    throw new HttpError(
      502,
      `GitHub rejected the token (${response.status}). It needs Actions write on the evaluation repo. ${detail}`,
    );
  }
  throw new HttpError(502, `GitHub ${response.status}: ${detail}`);
}

const SLUG = /^[A-Za-z0-9_.-]+$/;

function requiredRepo(name: string, value: string | undefined): string {
  const full = value?.trim() ?? "";
  if (!full) throw new HttpError(500, `${name} is not set.`);
  parseRepo(full);
  return full;
}

function parseRepo(full: string): { owner: string; repo: string } {
  const [owner, repo, extra] = full.split("/");
  if (!owner || !repo || extra || !SLUG.test(owner) || !SLUG.test(repo)) {
    throw new HttpError(500, `Invalid owner/name: ${full}`);
  }
  return { owner, repo };
}
