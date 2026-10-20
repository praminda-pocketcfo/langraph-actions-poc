# Submission portal

Small TanStack Start app. A learner uploads a project zip. The server stores that zip on Google Drive and dispatches `project-evaluation.yml` with the file's download link. The workflow downloads and unzips it. Nothing is pushed to a submission repository.

Drive is the submission store. GitHub Actions artifacts cannot be uploaded by the portal before a run exists, and they are deleted with the run. A few hundred internal submissions, kept under three months, fit in one Drive folder.

## Run locally

```bash
cd portal
npm install
cp .env.example .env
npm run dev
```

Open http://localhost:3000. `npm run check` runs the zip-filter tests. `npm run build` is the Vercel build.

## Drive setup

1. Create a service account and enable the Google Drive API.
2. Create a folder in a person's My Drive, or use a Shared Drive. Service accounts have no storage quota.
3. Share that folder with the service account email as Editor.
4. Put the folder id in `GDRIVE_ROOT_FOLDER_ID`.
5. Put the key in `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` for the portal.
6. Put the same JSON, as raw JSON, in the evaluation repo's Actions secret `GOOGLE_SERVICE_ACCOUNT_JSON`. The workflow uses it to download the file. The pytest step clears that variable before learner code runs.

Each upload becomes `<learner id>/<project id>/<evaluation id>.zip`. The folder stays private to the Drive owner and the service account. The workflow downloads the file with the Drive client and that same account.

On Vercel, set the project **Root Directory** to `portal` and add the same variables.

## Limits

Zip uploads are capped at 4 MB so they fit a Vercel function body. There is no sign-in and no Neon insert in this POC. The evaluation id is generated here and passed through to the workflow. Drive does not delete the zip on its own.
