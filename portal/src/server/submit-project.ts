import { dispatchEvaluation, publishSubmission, readConfig, type SubmitMode } from "./github";
import { HttpError } from "./http-error";
import { extractProjectZip, MAX_ZIP_BYTES } from "./zip";

export type SubmitResult = {
  evaluationId: string;
  mode: SubmitMode;
  learnerId: string;
  courseId: string;
  projectId: string;
  submissionRepo: string;
  branch: string;
  commitSha: string;
  pullRequestNumber: number;
  pullRequestUrl: string;
  filesCommitted: string[];
  skipped: string[];
  workflowUrl: string;
  dispatched: boolean;
  dispatchError?: string;
  note: string;
};

export async function submitProject(form: FormData): Promise<SubmitResult> {
  const learnerId = textField(form, "learnerId", 80);
  const courseId = textField(form, "courseId", 80);
  const projectId = projectField(form);
  const mode = modeField(form);
  const zip = await zipField(form);
  const extracted = extractProjectZip(zip);
  const config = readConfig();
  const evaluationId = crypto.randomUUID();

  const published = await publishSubmission({
    config,
    mode,
    evaluationId,
    learnerId,
    courseId,
    projectId,
    files: extracted.files,
  });

  const workflowUrl = `https://github.com/${config.evalRepo}/actions/workflows/${encodeURIComponent(config.evalWorkflow)}`;
  let dispatched = true;
  let dispatchError: string | undefined;
  try {
    await dispatchEvaluation({
      config,
      evaluationId,
      submissionRepo: published.submissionRepo,
      pullRequestNumber: published.pullRequestNumber,
      projectId,
    });
  } catch (error) {
    dispatched = false;
    dispatchError = error instanceof Error ? error.message : "Workflow dispatch failed.";
  }

  return {
    evaluationId,
    mode,
    learnerId,
    courseId,
    projectId,
    submissionRepo: published.submissionRepo,
    branch: published.branch,
    commitSha: published.commitSha,
    pullRequestNumber: published.pullRequestNumber,
    pullRequestUrl: published.pullRequestUrl,
    filesCommitted: extracted.files.map((file) => file.path),
    skipped: extracted.skipped.slice(0, 40),
    workflowUrl,
    dispatched,
    dispatchError,
    note: modeNote(mode, published.submissionRepo === config.evalRepo),
  };
}

function modeNote(mode: SubmitMode, sameRepo: boolean): string {
  if (sameRepo) {
    return "This pull request is on the evaluation repo. The workflow can read it with the default Actions token. Learner files now exist on the repo that holds the model key.";
  }
  if (mode === "repo") {
    return "The evaluation repo needs a SUBMISSION_TOKEN that can read this new repository. A fine-grained token limited to older repos will not see it, and the grader will fail when it fetches files.";
  }
  return "If this is not the evaluation repo, set SUBMISSION_TOKEN there so the workflow can read the pull request and comment on it.";
}

function textField(form: FormData, name: string, max: number): string {
  const value = form.get(name);
  if (typeof value !== "string") {
    throw new HttpError(400, `${name} is required.`);
  }
  const trimmed = value.trim();
  if (!trimmed || trimmed.length > max || /[\r\n]/.test(trimmed)) {
    throw new HttpError(400, `${name} must be 1–${max} characters on one line.`);
  }
  return trimmed;
}

function projectField(form: FormData): string {
  const projectId = textField(form, "projectId", 64);
  if (!/^[a-z0-9_-]+$/.test(projectId)) {
    throw new HttpError(400, "projectId must be a pack id such as word_counter.");
  }
  return projectId;
}

function modeField(form: FormData): SubmitMode {
  const mode = form.get("mode");
  if (mode === "branch" || mode === "repo") return mode;
  throw new HttpError(400, "Choose a branch in the configured repo, or a new private repo.");
}

async function zipField(form: FormData): Promise<Uint8Array> {
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) {
    throw new HttpError(400, "Choose a .zip of the project.");
  }
  if (!file.name.toLowerCase().endsWith(".zip")) {
    throw new HttpError(400, "The upload must be a .zip file.");
  }
  if (file.size > MAX_ZIP_BYTES) {
    throw new HttpError(400, "Zip must be 4 MB or smaller.");
  }
  return new Uint8Array(await file.arrayBuffer());
}
