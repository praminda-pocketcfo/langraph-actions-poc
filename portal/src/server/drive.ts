import { Readable } from "node:stream";
import { auth, drive } from "@googleapis/drive";
import { HttpError } from "./http-error";

const DRIVE_SCOPE = "https://www.googleapis.com/auth/drive";

type ServiceAccount = {
  client_email: string;
  private_key: string;
};

type DriveClient = ReturnType<typeof drive>;

export type DriveUpload = {
  folderId: string;
  folderUrl: string;
  fileId: string;
  downloadUrl: string;
};

export async function uploadSubmissionZip(input: {
  learnerId: string;
  projectId: string;
  evaluationId: string;
  zip: Uint8Array;
}): Promise<DriveUpload> {
  const account = loadServiceAccount();
  const rootId = process.env.GDRIVE_ROOT_FOLDER_ID?.trim() ?? "";
  if (!rootId) {
    throw new HttpError(500, "GDRIVE_ROOT_FOLDER_ID is not set.");
  }
  const client = drive({
    version: "v3",
    auth: new auth.GoogleAuth({
      credentials: account,
      scopes: [DRIVE_SCOPE],
    }),
  });
  const learnerFolder = await findOrCreateFolder(client, rootId, input.learnerId);
  const projectFolder = await findOrCreateFolder(client, learnerFolder, input.projectId);
  const fileId = await uploadFile(client, projectFolder, `${input.evaluationId}.zip`, input.zip);
  return {
    folderId: projectFolder,
    folderUrl: `https://drive.google.com/drive/folders/${projectFolder}`,
    fileId,
    downloadUrl: `https://drive.google.com/file/d/${fileId}/view`,
  };
}

function loadServiceAccount(): ServiceAccount {
  const encoded = process.env.GOOGLE_SERVICE_ACCOUNT_JSON_BASE64?.trim();
  const raw = process.env.GOOGLE_SERVICE_ACCOUNT_JSON?.trim();
  const text = encoded ? Buffer.from(encoded, "base64").toString("utf8") : raw;
  if (!text) {
    throw new HttpError(
      500,
      "Set GOOGLE_SERVICE_ACCOUNT_JSON_BASE64 or GOOGLE_SERVICE_ACCOUNT_JSON.",
    );
  }
  let parsed: ServiceAccount;
  try {
    parsed = JSON.parse(text) as ServiceAccount;
  } catch {
    throw new HttpError(500, "The Google service account JSON could not be parsed.");
  }
  if (!parsed.client_email || !parsed.private_key) {
    throw new HttpError(500, "Service account JSON needs client_email and private_key.");
  }
  return parsed;
}

async function findOrCreateFolder(client: DriveClient, parentId: string, name: string): Promise<string> {
  const query = [
    `name = '${escapeQuery(name)}'`,
    "mimeType = 'application/vnd.google-apps.folder'",
    `'${escapeQuery(parentId)}' in parents`,
    "trashed = false",
  ].join(" and ");
  const listed = await client.files.list({
    q: query,
    fields: "files(id)",
    pageSize: 1,
    supportsAllDrives: true,
    includeItemsFromAllDrives: true,
  });
  const existing = listed.data.files?.[0]?.id;
  if (existing) return existing;
  const created = await client.files.create({
    requestBody: {
      name,
      mimeType: "application/vnd.google-apps.folder",
      parents: [parentId],
    },
    fields: "id",
    supportsAllDrives: true,
  });
  if (!created.data.id) {
    throw new HttpError(502, `Drive did not return an id for folder ${name}.`);
  }
  return created.data.id;
}

async function uploadFile(
  client: DriveClient,
  parentId: string,
  name: string,
  bytes: Uint8Array,
): Promise<string> {
  const created = await client.files.create({
    requestBody: { name, parents: [parentId] },
    media: {
      mimeType: "application/zip",
      body: Readable.from(Buffer.from(bytes)),
    },
    fields: "id",
    supportsAllDrives: true,
  });
  if (!created.data.id) {
    throw new HttpError(502, "Drive did not return an id for the uploaded zip.");
  }
  return created.data.id;
}

function escapeQuery(value: string): string {
  return value.replaceAll("\\", "\\\\").replaceAll("'", "\\'");
}
