# Analytics measurement

`static/analytics.js` owns the GA4 bootstrap and custom event schema. Each HTML
template loads it once. Collection runs only on HTTPS `legalhashchecksum.com`
and `www.legalhashchecksum.com`, on the public routes in its tool map. Local
previews, unknown routes and the moderation panel do not initialize GA.
Loading the helper twice does not initialize it twice. Page configuration waits
for the document title. Calls use optional chaining so blocking analytics does
not stop calculations, hashing or native printing.

## Events to use in reports

All custom events include a canonical `tool` identifier derived from the route.

| Event | Meaning | Additional fields |
| --- | --- | --- |
| `file_selected` | A nonempty file picker selection or drop on the hash tool | `file_count` |
| `hash_completed` | One hashing operation completed with at least one successful file | `file_count` of successful files, `algorithm_count`, `result` (`complete` or `partial`) |
| `hash_failed` | A hashing operation produced no successful files | `file_count` (0), `algorithm_count` |
| `file_loaded` | The verification tool finished reading and hashing a file | None |
| `hash_verified` | A full hexadecimal expected hash was compared with the selected file | `result` (`match` or `mismatch`) |
| `certificate_prepared` | A Part A/B certificate preview was built | `part`, `has_hash_report` |
| `invoice_prepared` | An invoice preview was built | None |
| `print_requested` | The browser raised `beforeprint`; duplicate notifications during one dialog are suppressed | `part` for a prepared certificate, `format` for bail bond/vakalatnama |
| `calculate` | An explicit Calculate action produced a valid result | None |
| `tool_open` | A directory card was clicked | `destination` |
| `tool_search` | A nonempty tool search settled after its debounce | `has_query`, optional `law` |
| `filter_category` | A directory/dictionary category was selected | `category` |
| `select_law` | A law converter tab was selected | `law` |
| `j_filter` | A judgment listing/filter request succeeded | `area`, `days`, `year`, `has_query`, `has_court` |
| `feedback_sent` | The feedback endpoint acknowledged success | `has_email`, optional `type` |

`hash_completed` counts operations; sum `file_count` to measure successful files.
A batch with some failed files has `result=partial`. Verification suppresses
immediate repeats for the same file and expected hash and ignores partial typing.
Calculator input/change previews and invalid Calculate clicks are not counted.

`print_requested` is **not a saved PDF or completed download**. The browser does
not tell this app whether the person saved, printed or cancelled. Replace old
`generate_certificate` / `print_document` charts with the new, separate preview
and print metrics. Retained `download_png` events are legacy download attempts,
not confirmation that a file was saved.

Other retained interaction events are `j_click`, `theme_toggle`, `expand_section`,
`filter_chapter`, `open_helplines`, `helpline_click`, and `external_link`.
Only allowlisted enums, bounded counts and Boolean flags are retained. Unlisted
fields are dropped, including raw queries, document text, file names, hashes,
claim amounts, client details, email addresses and arbitrary URLs. Tool searches
no longer write raw `q` into the directory URL. Configured page locations omit
query strings and fragments except validated UTM source/medium/campaign/content
tokens; configured referrers retain HTTPS origins only and exclude localhost.

## GA4 and dashboard follow-up

These source changes do not alter the GA4 property or Data Studio report.

1. Review the web stream's Enhanced Measurement settings, especially automatic
   form interactions and site search. Those Google-managed events are separate
   from this helper's custom-event allowlist; do not enable automatic collection
   of legal form inputs or private search strings.
2. Register event-scoped dimensions such as `tool`, `destination`, `part`,
   `format` and `result` if needed in the report. Choose business key events
   deliberately; `certificate_prepared` measures preparation, not revenue.
3. Filter staff visits to the live domain separately. Local previews are now
   excluded in code, but this does not identify staff browsing the real site.
   Validate GA4 internal-traffic filters in Testing before activating them.
4. Compare a consistent period after deployment (for example 28 days). Historical
   duplicate events and local-preview traffic cannot be repaired by this patch.
   Label date-range user totals accurately; the screenshots' multi-month range
   must not be labelled Monthly Users. Verify the return-rate formula separately.

No `purchase` event or revenue value is emitted by this patch. Record purchases
only after a real gateway payment has been verified by the backend.

## Local regression

Use the application environment for the server. The elevated local rate limit
below is solely for the test process, not a production configuration change:

```sh
python -c 'import main,uvicorn; main.RATE_LIMIT=500; uvicorn.run(main.app,host="127.0.0.1",port=18515)'
python tests/analytics_smoke.py --base-url http://127.0.0.1:18515 --browser '/path/to/chrome'
```

The test requires Playwright. It serves real application pages under a simulated
production origin, substitutes an empty Google script and blocks offsite
requests. It checks the queued GA commands without sending hits to GA4, uses
synthetic files and feedback responses, and never sends email or production
feedback. It also verifies local exclusion and calculator operation with the
analytics helper blocked. Actual GA4 ingestion, property settings and dashboard
formulas need account-level verification after deployment.
