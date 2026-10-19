import { createFileRoute } from "@tanstack/react-router";
import { HttpError } from "../../server/http-error";
import { submitProject } from "../../server/submit-project";

export const Route = createFileRoute("/api/submit")({
  server: {
    handlers: {
      POST: async ({ request }) => {
        try {
          const form = await request.formData();
          const result = await submitProject(form);
          return Response.json(result);
        } catch (error) {
          const status = error instanceof HttpError ? error.status : 500;
          const message = error instanceof Error ? error.message : "Upload failed.";
          console.error("Submit error", error);
          return Response.json({ error: message }, { status });
        }
      },
    },
  },
});
