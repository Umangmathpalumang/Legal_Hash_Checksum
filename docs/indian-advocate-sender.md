# Indian advocate directory sender

This is a separate, one-time introduction campaign for `indian-advocate-directories.xlsx`. It reuses the existing send-only Gmail OAuth connection in `~/lhc/token.json`. It never reads an inbox or rotates credentials. Import, preview, status, CSV export and dry-runs never connect to Gmail.

The original workbook is immutable input. A private SQLite ledger records contacts, individual attempts, timestamps, Gmail message IDs, and campaign runs. `send-status.csv` is an Excel-readable export of that ledger with the original source and page references. Recipient data and runtime files stay on the VPS and must not be committed to Git.

## Recipient selection

The import expects the `Sources` and `Emails for review` sheets and the eight existing contact headers in row 8. Only rows whose review note is exactly `Source and delivery review required` are eligible for the first-stage queue. Historical entries, suspicious spellings, shortened fragments, unknown source IDs, malformed addresses and formula cells are held or rejected. This does not establish deliverability or recipient consent.

Every contact in the Allahabad, Calcutta and LHC workbooks is reserved for its existing campaign, including unsent contacts. Their sent-state JSON files and shared blacklist are also checked. Missing, unreadable or changing exclusion data stops the new campaign. A fingerprint cache avoids repeatedly parsing unchanged workbooks while every delivery checks for changes. Local unsubscribes are excluded too.

An accepted Gmail response is not proof of inbox delivery. An `attempting` record is committed before a request is made. A successful response records the Gmail ID before the next recipient. Timeouts, server failures and crashes leave an uncertain/attempting record that is excluded from automatic retries. Definite client rejections are held. Authentication/quota rejections stop the batch and set a one-hour cooldown. Never remove these records simply to replay a batch.

## Defaults

- Paused until explicitly enabled.
- 12 recipients per batch and per IST clock hour.
- Maximum 108 attempts per IST day for this campaign, with a 15-second gap.
- Monday-Friday, 9 AM-5 PM, at minute 10 (`10 9-17 * * 1-5`) on the existing IST VPS.
- Existing campaign schedules are preserved.
- One introduction per eligible email address. There are no automatic follow-ups.

The limits apply to this campaign, not every message in the Gmail account. Gmail may impose separate limits. The sender stops on a quota response instead of switching accounts or transports.

## Install in paused mode

From the checkout containing the scripts:

```sh
python3 scripts/install-indian-advocate-sender.py --workbook /absolute/path/indian-advocate-directories.xlsx
```

The installer uploads the workbook and code, imports it, verifies a dry-run, exports the initial status CSV, installs the guarded schedule and updates the existing health monitor. It leaves `enabled=false`; the scheduled command cannot send while paused. Existing credentials, contacts and histories are not edited. Private rollback files are kept in `~/lhc/indian_advocates/backups/`.

## Review before activation

On the VPS:

```sh
~/lhc/venv/bin/python3 ~/lhc/indian_advocate_emailer.py preview
~/lhc/venv/bin/python3 ~/lhc/indian_advocate_emailer.py status
```

`preview` includes the subject, body and redacted recipient counts. It never sends. The subject is **Free legal tools for Indian advocates - feedback welcome**. The message introduces Legal Hash Checksum as a Hoursdev product, links to `/tools`, requests feedback and offers a reply-based opt-out. Replies are handled by the owner; the sender does not inspect the inbox or automatically process replies.

After the owner authorizes this new external campaign, enable future scheduled runs:

```sh
~/lhc/venv/bin/python3 ~/lhc/indian_advocate_emailer.py configure --enable
```

Explicit manual sending also requires an enabled configuration and working hours:

```sh
~/lhc/venv/bin/python3 ~/lhc/indian_advocate_emailer.py run --send
```

Omitting `--send` is always a dry-run. The health monitor reads this campaign's saved summary and reports missed runs, failures and uncertain delivery holds. A paused campaign is normal and does not trigger failure alerts.

## Maintain the campaign

```sh
~/lhc/venv/bin/python3 ~/lhc/indian_advocate_emailer.py configure --disable
~/lhc/venv/bin/python3 ~/lhc/indian_advocate_emailer.py unsubscribe --email advocate@example.com
~/lhc/venv/bin/python3 ~/lhc/indian_advocate_emailer.py export
```

The current exclusive lock lets an active batch finish before another command changes its configuration. Pause or unsubscribe commands issued during a batch return `campaign_already_running`; retry once the current batch finishes. The shared blacklist is rechecked before every request. Local unsubscribes apply to this new campaign only. Honour a global opt-out in the shared blacklist as well when the recipient requests it.

The exported file is `~/lhc/indian_advocates/send-status.csv`. The source workbook, accepted attempts and previous send histories survive repeated imports. Source rows removed from a later workbook are held instead of deleting their history.

## Verification

```sh
python3 -m unittest discover -s tests -p test_indian_advocate_emailer.py -v
python3 -m unittest discover -s tests -p test_directory_campaign_health.py -v
python3 -m unittest discover -s tests -p test_gmail_health.py -v
```

These tests use synthetic contacts and mocked Gmail responses. They do not read real credentials or send messages.

API references: [Gmail messages.send](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send) and [Gmail error handling](https://developers.google.com/workspace/gmail/api/guides/handle-errors).
