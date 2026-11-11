# Legal Hash Checksum

Run the web app locally from this directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8506
```

Open [Tools](http://127.0.0.1:8506/), [Dashboard](http://127.0.0.1:8506/dashboard), or [Hash](http://127.0.0.1:8506/hash). The install page at `/download` gives browser installation steps. Electron source and development instructions are in [desktop](desktop/README.md); native installers require a separate build.

The updated docket imports existing browser cases on the first visit from the same browser and site, and keeps the original records for rollback.

The dashboard and browser tools work without database credentials. Set these variables in the process environment or in a local, untracked `.env` file for the server features:

| Variable | Used for |
| --- | --- |
| `QA_DATABASE_URL` | PostgreSQL connection for Legal Q&A |
| `QA_ADMIN_PASSWORD` | Legal Q&A moderation access |
| `JUDGMENT_DATABASE_URL` | PostgreSQL connection for the judgment digest (requires the existing `judgments_dedup` view) |
| `GMAIL_USER`, `GMAIL_PASS`, `FEEDBACK_TO` | Optional email delivery for site feedback |

Set the database and moderation variables on the VPS before deploying this version. Rotate any credentials previously stored in source control.

Paid plans are shown as a preview. The checkout and billing policy mockups in [docs/payment-drafts](docs/payment-drafts) are not served by the app. Payment verification, subscriptions, and native releases are separate work.

GitHub Actions deploys pushes to `main` to the VPS.
