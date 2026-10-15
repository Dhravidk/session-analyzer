# Ally Session Analyzer — Jev parallel version

Retired experiment, retained as development history. Jev is not approved for this project; use the baseline at the repository root. This directory is excluded from the current plugin package. The instructions below describe the original experiment, not the supported workflow.

Version A is the baseline analyzer at the repository root. Version B lives here
and imports that same engine. It adds Jev prompt classifications and finding
priorities. Parsing, deduplication, token accounting, rules, canonical exports,
and the baseline HTML template are shared, not independently reimplemented.

This is a functional integration, not a validated claim that Jev improves the
team's analysis. Live quality and speed must be measured on representative work.

## Try the matched reports

From the repository root, with Python 3.9 or later:

```sh
python3 variants/jev/run.py --data-dir .analysis/jev-ab/store compare "/path/to/session.log" \
  --output .analysis/jev-ab/preview --config variants/jev/config.example.json
```

Open the resulting `index.html`. It links to A and B and includes a feedback CSV
and a comparison manifest. This default command is local only: B says **not run**
until real Jev answers exist. No simulated scores are presented to reviewers.

For a live comparison, set `TYPESAFE_API_KEY` securely in the process environment
and use a funded TypeSafe account. The key is never accepted in transcript data,
written to reports, or stored by this extension. Then run:

```sh
python3 variants/jev/run.py --data-dir .analysis/jev-ab/store compare "/path/to/session.log" \
  --output .analysis/jev-ab/live-01 --config variants/jev/config.example.json --live --fresh
```

`config.example.json` enables bounded transcript excerpts sent to the official
TypeSafe endpoint. Use this with the team's approved service and data policy.
Without a config file the default is metadata only, which disables prompt
classification. Pattern redaction removes some common credentials, email
addresses and home-directory names; it does not guarantee anonymization or
remove all proprietary code. Add operator-authored redaction expressions when
appropriate. Thinking blocks, images, attachments and environment fields are
excluded. Full transcripts are never sent as a single request.

The output directory must be new. `--fresh` ignores saved Jev answers; omitting
it permits cache reuse and reports cache hits explicitly. The comparison uses
one identical canonical result for A and B and records whether baseline import
or analysis was cached. Shared core work is measured once; Jev time and usage are
additional. This measures an added interpretation layer, not a replacement for
an existing large-model pass. Analyst review time is a separate team measurement.

## Same commands, with an added interpretation stage

All baseline commands are available through `python3 variants/jev/run.py` or
the installed `ally-session-jev` command. `run` and `analyze` compute the same
baseline and then invoke Jev. Add `--skip-jev` for the exact baseline path.

```sh
python3 variants/jev/run.py run "/path/to/session.log" \
  --jev-config variants/jev/config.example.json --output "/path/to/B.html"

python3 variants/jev/run.py jev-preview ANALYSIS_ID --config variants/jev/config.example.json
python3 variants/jev/run.py jev-interpret ANALYSIS_ID --config variants/jev/config.example.json --fresh
python3 variants/jev/run.py jev-results JEV_RUN_ID
python3 variants/jev/run.py jev-export JEV_RUN_ID "/path/to/B.html"
```

Use the same `--data-dir` before the subcommand when querying an existing store.
An optional installation into a virtual environment is `python3 -m pip install
-e . -e variants/jev` from the root. Running from source requires no third-party
runtime packages or installation.

For HTML, B renders the baseline template and adds a separate Jev review panel.
The original Download analysis JSON button still returns canonical data.
Jev JSON has its own download. JSON/CSV exports through `run` retain the baseline
format and receive a separate `.jev.json` companion. All reports remain offline
and exclude source excerpts. Failed Jev runs retain baseline output; the CLI
returns exit status 3 for partial/unavailable Jev results, 2 for invalid input,
and 0 for complete or explicitly local-only work.

## What Jev does

- Classifies selected prompt messages as correction, clarification, changed
  requirement, new requirement, other, or insufficient evidence. Unknown sender
  origin stays unknown: a user-role message is not automatically a human action.
- Assigns a 0–3 **review priority** to existing findings using sampled context,
  with an independent evidence-sufficiency judgment. It never changes rule
  severity or hides findings.
- Keeps probability, distribution confidence, uncertainty, evidence IDs, model
  version, question version, failures and coverage visible.

The default cap is 200 findings and 200 prompt messages, chosen by deterministic
round robin across sessions. This is not a random statistical sample. Each
request has at most eight contextual records with 1,400 characters per excerpt;
a 30,000-byte request cap can remove older context and records those removals.
Question types referring to the same evidence share a request. The default
worker limit is four. Account errors stop further queued requests; already
in-flight requests may finish. Rate-limit/overload retries are bounded. Timeouts
are not automatically repeated because a timed-out POST may have been processed.

The default model is pinned to `jev-1.13.0`. Moving aliases are rejected so an
A/B run does not silently change models. Saved answers are reused only for the
same model, complete prepared payload and question version. Threshold changes
re-evaluate the review disposition using the stored distribution.

Run manifests and redacted request plans are stored privately beneath
`DATA_DIR/jev/runs/`; cached answers are beneath `DATA_DIR/jev/cache/`. They are
separate from baseline SQLite tables and human review annotations. Treat the
request plans as source excerpts; do not share the entire private data directory.

## Claude Code plugin

The source plugin is `variants/jev`; its name and server are
`ally-session-analyzer-jev`, so A can remain installed alongside it. Launch with:

```sh
claude --plugin-dir "/absolute/path/to/Ally-Session Analyzer/variants/jev"
```

Run `/ally-session-analyzer-jev:analyze` with a selected source. The server exposes
all baseline tools unchanged and adds `jev_preview`, `jev_interpret`,
`jev_get_run`, `jev_get_annotations` and `jev_export_report`.

Remote calls from MCP are disabled until the operator sets `ALLY_JEV_ENABLED=1`
in the launching environment. Set `TYPESAFE_API_KEY` there and optionally
`ALLY_JEV_CONFIG` to an absolute configuration path. No tool can enable itself,
choose a different remote endpoint or accept a credential. Baseline operations
and reading existing Jev runs work without network enablement. Raw excerpts
returned to the calling agent still follow the baseline's separate disclosure
policy.

## Package both versions for the team

```sh
python3 variants/jev/build_bundles.py --output .analysis/jev-ab/packages
```

This produces standalone A and B plugin ZIPs with byte-identical baseline source
and a hash manifest. It includes no session logs, API keys, stores or reports.
Extract each ZIP and follow its `START_HERE.txt`. Rebuild both archives together
after changes to the baseline, then use the same input, profile and rate card.
The generated B bundle includes a captured copy of the baseline for portability;
the development source continues to share the original engine.

## Verification and A/B evaluation

```sh
python3 -m unittest discover -s variants/jev/tests -v
```

Tests use synthetic logs and simulated API responses. They check canonical
parity, response validation, redaction, uncertainty handling, caching, billing
failure, rate-limit retries, CLI export, and MCP policy. They do not measure
Jev's judgment accuracy. The console test attempted on October 13, 2026 accepted
five synthetic questions but returned “Your organization is out of funds.” No
model result or live latency was obtained; the test remains ready in the console.

For team review, alternate A-first and B-first, use identical tasks and inputs,
and record useful findings, false positives, missed issues, review time, trust
and preference in the included CSV. Keep uncertain predictions visible. Do not
report model improvements until you have actual judgments and reviewer results.

API contract verified against [TypeSafe API](https://docs.typesafe.ai/api),
[version and pricing](https://docs.typesafe.ai/models), and
[confidence semantics](https://docs.typesafe.ai/confidence) on October 13, 2026.
The successful-request cost estimate uses the published $0.042/M input rate for
the pinned model. Unknown model rates stay unpriced; failed and retried requests
may incur charges not included in returned usage.
