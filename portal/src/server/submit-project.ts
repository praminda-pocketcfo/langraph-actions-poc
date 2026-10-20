import { uploadSubmissionZip } from "./drive";
import { dispatchEvaluation, readConfig } from "./github";
import { HttpError } from "./http-error";
import { MAX_ZIP_BYTES } from "./zip";

export type SubmitResult = {
  evaluationId: string;
  learnerId: string;
  courseId: string;
  projectId: string;
  folderUrl: string;
  downloadUrl: string;
  workflowUrl: string;
  dispatched: boolean;
  dispatchError?: string;
};

export async function submitProject(form: FormData): Promise<SubmitResult> {
  const learnerId = textField(form, "learnerId", 80);
  const courseId = textField(form, "courseId", 80);
  const projectId = projectField(form);
  const zip = await zipField(form);
  const config = readConfig();
  const evaluationId = crypto.randomUUID();
  const uploaded = await uploadSubmissionZip({
    learnerId,
    projectId,
    evaluationId,
    zip,
  });

  const workflowUrl = `https://github.com/${config.evalRepo}/actions/workflows/${encodeURIComponent(config.evalWorkflow)}`;
  let dispatched = true;
  let dispatchError: string | undefined;
  try {
    await dispatchEvaluation({
      config,
      evaluationId,
      projectId,
      submissionUrl: uploaded.downloadUrl,
    });
  } catch (error) {
    dispatched = false;
    dispatchError = error instanceof Error ? error.message : "Workflow dispatch failed.";
  }

  return {
    evaluationId,
    learnerId,
    courseId,
    projectId,
    folderUrl: uploaded.folderUrl,
    downloadUrl: uploaded.downloadUrl,
    workflowUrl,
    dispatched,
    dispatchError,
  };
}

function textField(form: FormData, name: string, max: number): string {
  const value = form.get(name);
  if (typeof value !== "string") {
    throw new HttpError(400, `${name} is required.`);
  }
  const trimmed = value.trim();
  if (!trimmed || trimmed.length > max || /[\r\n/\\]/.test(trimmed)) {
    throw new HttpError(400, `${name} must be 1–${max} characters on one line, without slashes.`);
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
  const bytes = new Uint8Array(await file.arrayBuffer());
  if (bytes.length < 4 || bytes[0] !== 0x50 || bytes[1] !== 0x4b) {
    throw new HttpError(400, "That file is not a zip archive.");
  }
  return bytes;
}
