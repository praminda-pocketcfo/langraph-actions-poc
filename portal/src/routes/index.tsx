import { createFileRoute } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";

type SubmitResult = {
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
        Zip the local project and upload it. The server stores that zip in a
        Google Drive folder named with your learner id and project id, then
        starts evaluation. The workflow downloads the zip with the same service
        account. It does not push the project to a GitHub repository.
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
            4 MB max.
          </span>
          <input name="file" type="file" required accept=".zip,application/zip" />
        </label>

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
  return (
    <section className="result" role="status">
      <h2>{result.dispatched ? "Evaluation started" : "Uploaded, dispatch failed"}</h2>
      <dl>
        <dt>Evaluation</dt>
        <dd>{result.evaluationId}</dd>
        <dt>Learner</dt>
        <dd>{result.learnerId}</dd>
        <dt>Project</dt>
        <dd>{result.projectId}</dd>
        <dt>Drive folder</dt>
        <dd>
          <a href={result.folderUrl}>{result.learnerId}/{result.projectId}</a>
        </dd>
        <dt>Workflow</dt>
        <dd>
          <a href={result.workflowUrl}>project-evaluation.yml</a>
        </dd>
      </dl>
      {result.dispatchError ? <p className="note">{result.dispatchError}</p> : null}
      <p className="note">
        GitHub accepts the dispatch with an empty 204 response, so this page
        does not get a run id. The run shows up on the workflow page within a
        few seconds.
      </p>
    </section>
  );
}
