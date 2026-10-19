import { HttpError } from "./http-error";
import type { PackedFile } from "./zip";

const API = "https://api.github.com";

export type SubmitMode = "branch" | "repo";

export type PortalConfig = {
  token: string;
  submissionRepo: string | null;
  baseBranch: string | null;
  evalRepo: string;
  evalWorkflow: string;
  evalRef: string;
  org: string | null;
};

export type PublishedSubmission = {
  submissionRepo: string;
  branch: string;
  commitSha: string;
  pullRequestNumber: number;
  pullRequestUrl: string;
  baseBranch: string;
};

type GitHubErrorBody = {
  message?: string;
  errors?: Array<{ message?: string }>;
};

export function readConfig(): PortalConfig {
  const token = process.env.GITHUB_TOKEN?.trim() ?? "";
  if (!token) {
    throw new HttpError(500, "GITHUB_TOKEN is not set on the server.");
  }
  const evalRepo = requiredRepo(
    "GITHUB_EVAL_REPO",
    process.env.GITHUB_EVAL_REPO,
  );
  const submissionRepo = process.env.GITHUB_SUBMISSION_REPO?.trim() || null;
  if (submissionRepo) parseRepo(submissionRepo);
  const org = process.env.GITHUB_ORG?.trim() || null;
  if (org && !isSlug(org)) {
    throw new HttpError(500, "GITHUB_ORG is not a valid GitHub name.");
  }
  return {
    token,
    submissionRepo,
    baseBranch: process.env.GITHUB_SUBMISSION_BASE?.trim() || null,
    evalRepo,
    evalWorkflow: process.env.GITHUB_EVAL_WORKFLOW?.trim() || "project-evaluation.yml",
    evalRef: process.env.GITHUB_EVAL_REF?.trim() || "main",
    org,
  };
}

export async function publishSubmission(input: {
  config: PortalConfig;
  mode: SubmitMode;
  evaluationId: string;
  learnerId: string;
  courseId: string;
  projectId: string;
  files: PackedFile[];
}): Promise<PublishedSubmission> {
  const { config } = input;
  const branch = `submissions/${input.evaluationId}`;
  const repo =
    input.mode === "repo"
      ? await createPrivateRepo(config, input.evaluationId, input.projectId)
      : requireSubmissionRepo(config);

  console.log("config", config);
  const meta = await getRepo(config.token, repo);
  if (!meta.private) {
    if (input.mode === "repo") {
      await deleteRepoBestEffort(config.token, repo);
    }
    throw new HttpError(
      400,
      `${repo.owner}/${repo.repo} is public. Refusing to upload learner code.`,
    );
  }

  const baseBranch = config.baseBranch || meta.default_branch || "main";
  const base = await getBranchTip(config.token, repo, baseBranch);
  const commitSha = await commitFiles({
    token: config.token,
    repo,
    parentSha: base.commitSha,
    baseTreeSha: base.treeSha,
    branch,
    message: commitMessage(input),
    files: input.files,
  });
  const pull = await openDraftPull({
    token: config.token,
    repo,
    branch,
    baseBranch,
    title: `Submission ${input.evaluationId}`,
    body: pullBody(input),
  });

  return {
    submissionRepo: `${repo.owner}/${repo.repo}`,
    branch,
    commitSha,
    pullRequestNumber: pull.number,
    pullRequestUrl: pull.html_url,
    baseBranch,
  };
}

export async function dispatchEvaluation(input: {
  config: PortalConfig;
  evaluationId: string;
  submissionRepo: string;
  pullRequestNumber: number;
  projectId: string;
}): Promise<void> {
  const repo = parseRepo(input.config.evalRepo);
  const workflow = encodeURIComponent(input.config.evalWorkflow);
  await github(input.config.token, "POST", `/repos/${repo.owner}/${repo.repo}/actions/workflows/${workflow}/dispatches`, {
    ref: input.config.evalRef,
    inputs: {
      evaluation_id: input.evaluationId,
      submission_repo: input.submissionRepo,
      pr_number: String(input.pullRequestNumber),
      project_id: input.projectId,
    },
  });
}

function requireSubmissionRepo(config: PortalConfig): RepoName {
  if (!config.submissionRepo) {
    throw new HttpError(
      500,
      "GITHUB_SUBMISSION_REPO is not set. Branch mode needs an existing private repository.",
    );
  }
  return parseRepo(config.submissionRepo);
}

async function createPrivateRepo(
  config: PortalConfig,
  evaluationId: string,
  projectId: string,
): Promise<RepoName> {
  const name = `learner-submission-${evaluationId}`;
  const body = {
    name,
    private: true,
    visibility: "private",
    auto_init: true,
    has_issues: false,
    has_wiki: false,
    has_projects: false,
    description: `Learner submission ${evaluationId} (${projectId}). Portal-owned. Learners are not collaborators.`,
  };
  const path = config.org
    ? `/orgs/${encodeURIComponent(config.org)}/repos`
    : "/user/repos";
  const created = await github<{
    full_name: string;
    private: boolean;
    default_branch: string;
  }>(config.token, "POST", path, body);

  const repo = parseRepo(created.full_name);
  if (!created.private) {
    await deleteRepoBestEffort(config.token, repo);
    throw new HttpError(
      500,
      `GitHub created a public repository (${created.full_name}). It was deleted if the token was allowed to.`,
    );
  }
  await waitForBranch(config.token, repo, created.default_branch || "main");
  return repo;
}

async function waitForBranch(token: string, repo: RepoName, branch: string): Promise<void> {
  let last = "the default branch was not ready";
  for (let attempt = 0; attempt < 8; attempt++) {
    try {
      await getBranchTip(token, repo, branch);
      return;
    } catch (error) {
      last = error instanceof Error ? error.message : last;
      await sleep(750);
    }
  }
  throw new HttpError(502, `Timed out waiting for ${repo.owner}/${repo.repo}: ${last}`);
}

type RepoName = { owner: string; repo: string };

type RepoMeta = { private: boolean; default_branch: string };

async function getRepo(token: string, repo: RepoName): Promise<RepoMeta> {
  return github<RepoMeta>(
    token,
    "GET",
    `/repos/${repo.owner}/${repo.repo}`,
  );
}

async function getBranchTip(
  token: string,
  repo: RepoName,
  branch: string,
): Promise<{ commitSha: string; treeSha: string }> {
  const ref = await github<{ object: { sha: string } }>(
    token,
    "GET",
    `/repos/${repo.owner}/${repo.repo}/git/ref/heads/${branch}`,
  );
  const commit = await github<{ tree: { sha: string } }>(
    token,
    "GET",
    `/repos/${repo.owner}/${repo.repo}/git/commits/${ref.object.sha}`,
  );
  return { commitSha: ref.object.sha, treeSha: commit.tree.sha };
}

async function commitFiles(input: {
  token: string;
  repo: RepoName;
  parentSha: string;
  baseTreeSha: string;
  branch: string;
  message: string;
  files: PackedFile[];
}): Promise<string> {
  const entries = await mapPool(input.files, 4, async (file) => ({
    path: file.path,
    mode: "100644" as const,
    type: "blob" as const,
    sha: await createBlob(input.token, input.repo, file.bytes),
  }));

  let treeSha = input.baseTreeSha;
  for (let i = 0; i < entries.length; i += 80) {
    const tree = await github<{ sha: string }>(
      input.token,
      "POST",
      `/repos/${input.repo.owner}/${input.repo.repo}/git/trees`,
      { base_tree: treeSha, tree: entries.slice(i, i + 80) },
    );
    treeSha = tree.sha;
  }

  const commit = await github<{ sha: string }>(
    input.token,
    "POST",
    `/repos/${input.repo.owner}/${input.repo.repo}/git/commits`,
    {
      message: input.message,
      tree: treeSha,
      parents: [input.parentSha],
    },
  );

  await github(
    input.token,
    "POST",
    `/repos/${input.repo.owner}/${input.repo.repo}/git/refs`,
    { ref: `refs/heads/${input.branch}`, sha: commit.sha },
  );
  return commit.sha;
}

async function createBlob(token: string, repo: RepoName, bytes: Uint8Array): Promise<string> {
  const body =
    bytes.byteLength === 0
      ? { content: "" }
      : { content: Buffer.from(bytes).toString("base64"), encoding: "base64" };
  const blob = await github<{ sha: string }>(
    token,
    "POST",
    `/repos/${repo.owner}/${repo.repo}/git/blobs`,
    body,
  );
  return blob.sha;
}

async function openDraftPull(input: {
  token: string;
  repo: RepoName;
  branch: string;
  baseBranch: string;
  title: string;
  body: string;
}): Promise<{ number: number; html_url: string }> {
  const path = `/repos/${input.repo.owner}/${input.repo.repo}/pulls`;
  const payload = {
    title: input.title,
    head: input.branch,
    base: input.baseBranch,
    body: input.body,
  };
  try {
    return await github(input.token, "POST", path, { ...payload, draft: true });
  } catch (error) {
    if (error instanceof HttpError && /draft/i.test(error.message)) {
      return github(input.token, "POST", path, payload);
    }
    throw error;
  }
}

async function deleteRepoBestEffort(token: string, repo: RepoName): Promise<void> {
  try {
    await github(token, "DELETE", `/repos/${repo.owner}/${repo.repo}`);
  } catch {
    // Best effort. The caller still refuses to store the upload.
  }
}

function commitMessage(input: {
  evaluationId: string;
  learnerId: string;
  courseId: string;
  projectId: string;
}): string {
  return [
    `Submission ${input.evaluationId}`,
    "",
    `learner: ${input.learnerId}`,
    `course: ${input.courseId}`,
    `project: ${input.projectId}`,
  ].join("\n");
}

function pullBody(input: {
  evaluationId: string;
  learnerId: string;
  courseId: string;
  projectId: string;
}): string {
  return [
    "Opened by the academy portal so project-evaluation.yml can read this head.",
    "The learner is not a collaborator on this repository.",
    "",
    `evaluation_id: ${input.evaluationId}`,
    `learner: ${input.learnerId}`,
    `course: ${input.courseId}`,
    `project: ${input.projectId}`,
  ].join("\n");
}

async function github<T>(
  token: string,
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  let response: Response | null = null;
  for (let attempt = 0; attempt < 2; attempt++) {
    response = await fetch(`${API}${path}`, {
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
    if (response.status !== 502 && response.status !== 503) break;
    await sleep(400);
  }
  if (!response) {
    throw new HttpError(502, "GitHub request failed before a response.");
  }
  if (!response.ok) {
    const status = response.status === 422 ? 400 : 502;
    throw new HttpError(status, await githubError(response, path));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function githubError(response: Response, path: string): Promise<string> {
  let detail = response.statusText;
  try {
    const body = (await response.json()) as GitHubErrorBody;
    const extra = (body.errors ?? [])
      .map((item) => item.message)
      .filter((item): item is string => Boolean(item));
    detail = [body.message, ...extra].filter(Boolean).join(": ");
  } catch {
    // GitHub sometimes returns an empty error body.
  }
  if (response.status === 401 || response.status === 403) {
    return `GitHub rejected the token (${response.status}). It needs contents and pull-request write on the submission repo, actions write on the evaluation repo, and repository creation for new-repo mode. ${detail}`;
  }
  if (response.status === 404) {
    return `GitHub returned 404 for ${path}. The repo may not exist, or the token cannot see it. ${detail}`;
  }
  return `GitHub ${response.status}: ${detail}`;
}

const SLUG = /^[A-Za-z0-9_.-]+$/;

function isSlug(value: string): boolean {
  return SLUG.test(value);
}

function requiredRepo(name: string, value: string | undefined): string {
  const full = value?.trim() ?? "";
  if (!full) throw new HttpError(500, `${name} is not set.`);
  parseRepo(full);
  return full;
}

function parseRepo(full: string): RepoName {
  const [owner, repo, extra] = full.split("/");
  if (!owner || !repo || extra || !isSlug(owner) || !isSlug(repo)) {
    throw new HttpError(500, `Invalid owner/name: ${full}`);
  }
  return { owner, repo };
}

async function mapPool<T, R>(
  items: T[],
  limit: number,
  fn: (item: T) => Promise<R>,
): Promise<R[]> {
  const results = new Array<R>(items.length);
  let next = 0;
  async function worker() {
    for (;;) {
      const index = next++;
      if (index >= items.length) return;
      results[index] = await fn(items[index] as T);
    }
  }
  const workers = Math.min(limit, items.length);
  await Promise.all(Array.from({ length: workers }, () => worker()));
  return results;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
