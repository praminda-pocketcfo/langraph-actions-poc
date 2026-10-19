import { unzipSync } from "fflate";
import { HttpError } from "./http-error.ts";

export const MAX_ZIP_BYTES = 4 * 1024 * 1024;
export const MAX_UNCOMPRESSED_BYTES = 12 * 1024 * 1024;
export const MAX_FILE_BYTES = 1024 * 1024;
export const MAX_FILES = 200;

const SKIP_SEGMENTS = new Set([
  ".git",
  "node_modules",
  "__pycache__",
  ".venv",
  "venv",
  "dist",
  "build",
  ".next",
  "__MACOSX",
  ".idea",
  ".vscode",
]);

export type PackedFile = {
  path: string;
  bytes: Uint8Array;
};

export type ZipExtract = {
  files: PackedFile[];
  skipped: string[];
};

export function extractProjectZip(zip: Uint8Array): ZipExtract {
  if (zip.byteLength === 0) {
    throw new HttpError(400, "The zip file is empty.");
  }
  if (zip.byteLength > MAX_ZIP_BYTES) {
    throw new HttpError(400, "Zip must be 4 MB or smaller.");
  }

  const declared = declaredUncompressedSize(zip);
  if (declared != null && declared > MAX_UNCOMPRESSED_BYTES) {
    throw new HttpError(
      400,
      "Zip expands past 12 MB. Remove dependencies and the .git folder before zipping.",
    );
  }

  let entries: Record<string, Uint8Array>;
  try {
    entries = unzipSync(zip);
  } catch {
    throw new HttpError(400, "Could not read that file as a zip archive.");
  }

  const skipped: string[] = [];
  const byPath = new Map<string, Uint8Array>();
  let uncompressed = 0;

  for (const [rawPath, bytes] of Object.entries(entries)) {
    const path = rawPath.replaceAll("\\", "/");
    if (!path || path.endsWith("/")) continue;

    const reason = skipReason(path);
    if (reason) {
      skipped.push(`${path} (${reason})`);
      continue;
    }
    assertSafe(path);
    uncompressed += bytes.byteLength;
    if (uncompressed > MAX_UNCOMPRESSED_BYTES) {
      throw new HttpError(400, "Zip expands past 12 MB.");
    }
    if (bytes.byteLength > MAX_FILE_BYTES) {
      throw new HttpError(400, `${path} is larger than 1 MB.`);
    }
    byPath.set(path, bytes);
  }

  let files = [...byPath.entries()].map(([path, bytes]) => ({ path, bytes }));
  files = stripSingleRoot(files);
  for (const file of files) assertSafe(file.path);

  if (files.length === 0) {
    throw new HttpError(
      400,
      "Zip has no project files after skipping .git, dependencies, and environment files.",
    );
  }
  if (files.length > MAX_FILES) {
    throw new HttpError(
      400,
      `Zip has ${files.length} files. The limit for this POC is ${MAX_FILES}.`,
    );
  }

  files.sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));
  return { files, skipped };
}

function skipReason(path: string): string | null {
  const parts = path.split("/");
  const base = parts[parts.length - 1] ?? "";
  if (parts.some((part) => SKIP_SEGMENTS.has(part))) return "ignored directory";
  if (base === ".DS_Store" || base === "Thumbs.db") return "os metadata";
  if (base === ".env" || base.startsWith(".env.")) return "environment file";
  if (base === "id_rsa" || base.endsWith(".pem") || base.endsWith(".key")) {
    return "key material";
  }
  return null;
}

function assertSafe(path: string): void {
  if (path.startsWith("/") || path.includes("\0")) {
    throw new HttpError(400, `Unsafe path in zip: ${path}`);
  }
  for (const part of path.split("/")) {
    if (part === "" || part === "." || part === "..") {
      throw new HttpError(400, `Unsafe path in zip: ${path}`);
    }
  }
}

function stripSingleRoot(files: PackedFile[]): PackedFile[] {
  if (files.length === 0) return files;
  const root = files[0]?.path.split("/")[0];
  if (!root) return files;
  if (!files.every((file) => file.path.startsWith(`${root}/`))) return files;
  return files.map((file) => ({
    ...file,
    path: file.path.slice(root.length + 1),
  }));
}

/** Sum of uncompressed sizes from the ZIP central directory, before inflate. */
function declaredUncompressedSize(zip: Uint8Array): number | null {
  const eocd = findEocd(zip);
  if (eocd < 0) return null;
  const view = new DataView(zip.buffer, zip.byteOffset, zip.byteLength);
  const count = view.getUint16(eocd + 10, true);
  let offset = view.getUint32(eocd + 16, true);
  if (count > 10_000) return MAX_UNCOMPRESSED_BYTES + 1;

  let total = 0;
  for (let i = 0; i < count; i++) {
    if (offset + 46 > zip.byteLength) return null;
    if (view.getUint32(offset, true) !== 0x02014b50) return null;
    const size = view.getUint32(offset + 24, true);
    if (size === 0xffffffff) return MAX_UNCOMPRESSED_BYTES + 1;
    total += size;
    const nameLen = view.getUint16(offset + 28, true);
    const extraLen = view.getUint16(offset + 30, true);
    const commentLen = view.getUint16(offset + 32, true);
    offset += 46 + nameLen + extraLen + commentLen;
  }
  return total;
}

function findEocd(zip: Uint8Array): number {
  const min = Math.max(0, zip.length - 22 - 65535);
  for (let i = zip.length - 22; i >= min; i--) {
    if (
      zip[i] === 0x50 &&
      zip[i + 1] === 0x4b &&
      zip[i + 2] === 0x05 &&
      zip[i + 3] === 0x06
    ) {
      return i;
    }
  }
  return -1;
}
