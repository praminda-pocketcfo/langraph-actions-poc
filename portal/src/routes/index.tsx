import { createFileRoute } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";

type SubmitResult = {
  evaluationId: string;
  mode: "branch" | "repo";
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

export const Route = createFileRoute("/")({
  component: Home,
});

function Home() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SubmitResult | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setPending(true);
    setError(null);
    setResult(null);
    try {
      const response = await fetch("/api/submit", {
        method: "POST",
        body: new FormData(form),
      });
      const payload = (await response.json()) as SubmitResult & { error?: string };
      if (!response.ok) {
        setError(payload.error ?? "Upload failed.");
        return;
      }
      setResult(payload);
      form.reset();
    } catch {
      setError("The server did not return a result.");
    } finally {
      setPending(false);
    }
  }

  return (
    <main>
      <h1>Submit a project</h1>
      <p className="lede">
        Zip the project you worked on and upload it. The server copies the files
        into a private GitHub repository with its own token, opens a draft pull
        request, and starts the evaluation workflow. Your GitHub user is not
        added to that repository, so you cannot browse other uploads.
      </p>

      <form onSubmit={onSubmit}>
        <label>
          <span className="label">Learner id</span>
          <input name="learnerId" type="text" required maxLength={80} placeholder="learner-1042" />
        </label>
        <label>
          <span className="label">Course id</span>
          <input name="courseId" type="text" required maxLength={80} defaultValue="demo-course" />
        </label>
        <label>
          <span className="label">Project id</span>
          <span className="hint">Must match a pack in the evaluation repo, for example word_counter.</span>
          <input name="projectId" type="text" required maxLength={64} defaultValue="word_counter" pattern="[a-z0-9_-]+" />
        </label>
        <label>
          <span className="label">Project zip</span>
          <span className="hint">
            4 MB max. A single wrapping folder is fine. .git, node_modules, and .env files are left out.
          </span>
          <input name="file" type="file" required accept=".zip,application/zip" />
        </label>

        <fieldset>
          <legend>Where it lands</legend>
          <label>
            <input type="radio" name="mode" value="branch" defaultChecked />
            <span>
              <span className="label">Branch in the configured private repo</span>
              <span className="hint">
                One repository, one branch and draft pull request per upload. Zero extra seats.
                Anyone later invited to that repo can read every submission.
              </span>
            </span>
          </label>
          <label>
            <input type="radio" name="mode" value="repo" />
            <span>
              <span className="label">New private repository</span>
              <span className="hint">
                A separate private repo for this upload. Still no collaborator invite.
                The evaluation token must be allowed to see newly created repos.
              </span>
            </span>
          </label>
        </fieldset>

        <button type="submit" disabled={pending}>
          {pending ? "Uploading…" : "Upload and evaluate"}
        </button>
      </form>

      {error ? (
        <div className="error" role="alert">
          {error}
        </div>
      ) : null}

      {result ? <Result result={result} /> : null}
    </main>
  );
}

function Result({ result }: { result: SubmitResult }) {
  const sample = result.filesCommitted.slice(0, 12);
  const extra = result.filesCommitted.length - sample.length;
  return (
    <section className="result" role="status">
      <h2>{result.dispatched ? "Evaluation started" : "Uploaded, dispatch failed"}</h2>
      <dl>
        <dt>Evaluation</dt>
        <dd>{result.evaluationId}</dd>
        <dt>Repository</dt>
        <dd>{result.submissionRepo}</dd>
        <dt>Branch</dt>
        <dd>{result.branch}</dd>
        <dt>Pull request</dt>
        <dd>
          <a href={result.pullRequestUrl}>#{result.pullRequestNumber}</a>
        </dd>
        <dt>Commit</dt>
        <dd>{result.commitSha.slice(0, 12)}</dd>
        <dt>Workflow</dt>
        <dd>
          <a href={result.workflowUrl}>project-evaluation.yml</a>
        </dd>
      </dl>
      <p className="note">{result.note}</p>
      {result.dispatchError ? <p className="note">{result.dispatchError}</p> : null}
      <p className="note">
        GitHub accepts the dispatch with an empty 204 response, so this page does
        not get a run id. The run shows up on the workflow page within a few seconds.
      </p>
      <ul className="files">
        {sample.map((path) => (
          <li key={path}>{path}</li>
        ))}
      </ul>
      {extra > 0 ? <p className="note">and {extra} more files</p> : null}
      {result.skipped.length > 0 ? (
        <p className="note">Skipped {result.skipped.length} paths (.git, dependencies, env files, or OS metadata).</p>
      ) : null}
    </section>
  );
}
