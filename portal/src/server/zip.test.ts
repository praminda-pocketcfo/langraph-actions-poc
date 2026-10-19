import assert from "node:assert/strict";
import test from "node:test";
import { zipSync, strToU8 } from "fflate";
import { extractProjectZip } from "./zip.ts";

const py = strToU8("def count_words(text):\n    return len(text.split())\n");

test("strips a single wrapping folder and drops git, deps, and env files", () => {
  const zip = zipSync({
    "my-repo/word_counter.py": py,
    "my-repo/README.md": strToU8("# hi\n"),
    "my-repo/.git/config": strToU8("[core]\n"),
    "my-repo/node_modules/leftpad/index.js": strToU8("module.exports = 1\n"),
    "my-repo/.env": strToU8("SECRET=1\n"),
    "my-repo/.DS_Store": strToU8("junk"),
  });

  const extracted = extractProjectZip(zip);
  assert.deepEqual(
    extracted.files.map((file) => file.path),
    ["README.md", "word_counter.py"],
  );
  assert.equal(extracted.skipped.length, 4);
});

test("keeps a top-level file when the zip is not a single folder", () => {
  const zip = zipSync({
    "word_counter.py": py,
    "notes/readme.txt": strToU8("notes\n"),
  });
  const extracted = extractProjectZip(zip);
  assert.deepEqual(
    extracted.files.map((file) => file.path),
    ["notes/readme.txt", "word_counter.py"],
  );
});

test("rejects path traversal", () => {
  const zip = zipSync({
    "../secret.txt": strToU8("nope\n"),
  });
  assert.throws(() => extractProjectZip(zip), /Unsafe path/);
});

test("rejects an archive that is not a zip", () => {
  assert.throws(
    () => extractProjectZip(strToU8("hello")),
    /Could not read that file as a zip/,
  );
});
