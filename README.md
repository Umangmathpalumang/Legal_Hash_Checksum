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

Feedback is sent to `FEEDBACK_TO` (or to `GMAIL_USER` when no destination is set). The API returns HTTP 503 if it cannot deliver. For the `cedrf` deployment, run `python3 scripts/update-feedback-gmail.py` from an interactive Terminal to replace a rejected Google app password. The helper tests Gmail authentication before updating the private service configuration and does not send a message.


Paid plans are shown as a preview. The checkout and billing policy mockups in [docs/payment-drafts](docs/payment-drafts) are not served by the app. Payment verification, subscriptions, and native releases are separate work.

GitHub Actions deploys pushes to `main` to the VPS.

### Browser PDF checks

With the app running locally, use `python tests/print_smoke.py --base-url http://127.0.0.1:8506 --output-dir /tmp/lhc-form-pdfs`. The script requires `playwright`, `pypdf`, and Playwright Chromium (or pass `--browser` with a Chrome executable). It fills the forms with synthetic data, generates PDFs, and checks the extracted text and page counts.

### Scheduled outreach Gmail recovery

The campaign mailers under `~/lhc` on `cedrf` use Gmail OAuth, separately from the website feedback app password. To check their shared token from your Mac, run `python3 scripts/reauthorize-outreach-gmail.py` with `google-auth-oauthlib` installed. If Google rejects the refresh grant, rerun with `--reauthorize` and sign in with the existing sender account. The helper requests only the previously granted send scope, verifies the refreshed credential, backs up the old token privately, and replaces it atomically. This restores the existing cron campaigns; the helper itself does not send a message, run a batch, or reset campaign history. The legacy Python 3.8 cron runtime should be upgraded separately after authentication is restored.

### Gmail health alerts

The `lhc-mail-health.timer` system service checks feedback SMTP sign-in, the existing outreach OAuth refresh grant, campaign scope definitions, and the latest scheduled campaign results every hour, around 15 minutes past the hour (IST). It runs independently of your Mac. It never runs a campaign, submits feedback, changes credentials, or reads the inbox. Its private state contains only redacted check results and notification timestamps.

Alerts go only to `umangmathpal@gmail.com`, with the relevant Mac Terminal command. The checker uses feedback SMTP when it works, or the existing send-only Gmail API grant when feedback SMTP is unavailable. A repeated incident gets at most one reminder per 24 hours; a notified incident gets one recovery email. If both credentials fail, email delivery is impossible through either connection. The separate Codex check reads the saved status and reports an undelivered alert, a stale check, or an unreachable VPS when that local automation is running.

From your Mac, run `python3 scripts/check-gmail-health.py --remote` to probe both connections without sending mail, or append `--status` to read the last saved check without contacting Google. `--notify` sends incident/recovery alerts; `--test-email` explicitly sends one setup test to the fixed owner address. Neither flag sends a campaign batch. Errors and status output exclude passwords, tokens, feedback text, and campaign recipient addresses.

The status includes a `campaigns` summary for Allahabad, Calcutta and LHC. It distinguishes failed runs, missed schedules (after a 15-minute grace period), incomplete runs, completed runs, and an empty eligible queue. CRM workbook corruption is shown separately from send failure. A successful authentication probe does not override a failed campaign result. Recorded sends mean the campaign logged Gmail acceptance; they do not establish inbox delivery. A saved status with `coverage=authentication_only` came from the earlier monitor and does not include these run checks.

The known legacy `invalid_scope` defect is a campaign asking for `gmail.readonly` when its shared token grants only `gmail.send`. From your Mac, `python3 scripts/repair-outreach-runtime.py --remote` previews the repair; append `--apply` to install the reviewed send-only scope and Calcutta recipient validation fixes. The helper backs up changed Python files privately under `~/lhc/.runtime-repair-backups`, verifies that credentials, contact workbooks, blacklist and sent history stay byte-for-byte unchanged, and never imports or runs a campaign. Malformed Calcutta recipient rows are skipped, without guessing replacement addresses or resetting their status. Unknown code layouts or permissions require review rather than an automatic rewrite.

For Allahabad recipient validation and CRM recovery, run `python3 scripts/repair-allahabad-crm.py --remote` to preview, then append `--apply` to install the reviewed repair. It preserves all literal source contacts and keeps the JSON sent history authoritative. A damaged workbook is backed up privately under `~/lhc/.crm-repair-backups` and rebuilt on the VPS using the app's existing openpyxl dependency (the VPS has no Node/artifact-tool runtime). The contacts sheet retains the `Allahabad HC Advocates` name, headers in row 2, contacts from row 3, and email in column D. `Send Log` is reconstructed from recorded send timestamps and message IDs; unavailable historical sequence/template values remain blank. Stored UTC timestamps are shown in IST. Every contact row and history email/message-ID pair is verified before installation. Credentials, blacklist and JSON history are verified unchanged. A healthy workbook is not rebuilt on reruns. The helper refuses to apply while a scheduled Allahabad batch is running.

The repaired Allahabad selector skips malformed addresses without deleting contacts or resetting statuses. The CRM writer records status, IST timestamp and Gmail message ID in the contact row and send log, then saves to a temporary workbook, validates the ZIP archive, checks for concurrent modification, and replaces the destination atomically. A failed save leaves the existing workbook intact. When upgrading an earlier repaired writer, the helper reconciles only the recorded status/time/message-ID fields and fills missing send-log IDs from the JSON history, preserving source contacts and other workbook content. Neither recovery helper imports a campaign entrypoint, sends mail, or changes cron schedules. A subsequent scheduled run is still required to confirm production sends and CRM updates together.

The VPS copies of the checker and the unit files live at `/home/ubuntu/.local/lib/lhc-mail-health/check-gmail-health.py` and `/etc/systemd/system/lhc-mail-health.{service,timer}`. Source units are in `scripts/systemd`. The state directory must exist at `/home/ubuntu/.local/state/lhc-mail-health` and be owned by `ubuntu` with mode 0700 before the service starts. Check the timer with `ssh cedrf systemctl status lhc-mail-health.timer`. To disable alerts, run `ssh cedrf sudo systemctl disable --now lhc-mail-health.timer`.

An app password should not need scheduled renewal; Google revokes app passwords after the Google Account password changes. OAuth is a different credential: an external Google OAuth app in **Testing** can issue refresh tokens that expire in seven days. The current publishing status has not been verified. Check the project's Google Auth Platform Audience settings before changing its status; any move out of Testing must meet Google's applicable requirements. Neither OAuth nor an app password can be guaranteed permanent or automatically restored after Google revokes access. For a production website, a separate transactional email provider under your domain can remove the dependency on a personal Gmail login, but requires provider credentials and domain verification.
