# Using Session Analyzer

Session Analyzer helps answer three questions about a Claude Code session:
what the captured work achieved, whether it followed material instructions,
and what the developer should do next. It also measures token usage, estimated
source-session cost, tool calls and recorded failures.

Python imports and measures the selected files locally. When you ask for a
written explanation, your approved Claude Code account reads controlled evidence
and writes the answer. A fresh native reviewer checks that answer against the
sources. Claude's interpretation can still be wrong; follow decisive citations.

Start with [installation](../INSTALL.md), including the `/analyze` shortcut.
Supporting skills are internal, so developers need only this command. The
0.23.2 candidate addresses [earlier live failures](release-live-audit-0.22.2.md);
installation alone is not evidence that every review is correct.

## Analyze one log

In Claude Code with the plugin loaded:

```text
/analyze /absolute/path/session.jsonl
```

Select the exact file. You can also ask a natural question such as “Analyze this
session: what was completed, what instructions were missed, and what should
change?” If controlled excerpts are not enabled, the analyzer can give metadata
but must leave prose-dependent task/compliance judgments unverified.

The default answer starts with estimated source-session cost and a token/dollar
breakdown. It then gives the recommendation or outcome, separate **Task outcome**
and **Instruction following** assessments, decisive evidence and supported changes.
A useful result may recommend a check or no persistent change. The analyzer must
not invent a skill edit to make an answer sound actionable.

## Analyze several logs

```text
/analyze /absolute/path/one.jsonl /absolute/path/two.jsonl
```

This produces a combined handoff while checking each session separately. For
separate answers in the same reply:

```text
/analyze /absolute/path/one.jsonl /absolute/path/two.jsonl --separate
```

`--separate` is part of the skill's request, not a flag to the `claude` executable.
The reviewer checks the selected collection in one pass; separate output does
not require a whole new review per log. See [selection and scope details](multiple-logs.md).

Use the same command for follow-ups, for example `/analyze what instructions were
missed?` in the existing analysis. `/analyze --report /path/session.jsonl` requests
a full saved investigation; `/analyze --browse /path/selected-directory` opens the
local browser. These are choices within the one entrypoint.

## Read the cost line correctly

- Input includes ordinary input, cache writes and cache reads. Do not add the
  cached portion again to the inclusive input total.
- Reasoning, when separately reported, is already inside output. Missing
  reasoning telemetry stays unavailable; it is not guessed from visible text.
- Source cost is a public-API token-price estimate using a dated bundled card.
  It is not a subscription invoice. Unknown prices or usage stay explicit.
- The opening excludes the analyzer and reviewer's own usage. Those are separate
  model calls through your Claude account.
- If two selected logs contain the same captured response, the combined figure
  counts that response once. Individual totals may include the same history.
  Running dollar snapshots inside logs are not separate charges to sum.

The default developer answer keeps resource diagnosis on request. For a focused
follow-up, ask “How many cached-input tokens were recorded?” or “Which compaction
events are actually captured?” Those tools remain available without rewriting
the earlier answer.

## Understand task and compliance judgments

An assistant saying “done” is a participant statement. A successful command
proves that command's result, with its actual selectors and revision; it does
not prove the whole task passed. A missing final result is unverified, not
automatically a failed action.

Approval before implementation remains required where the original workflow
requires it. Writing a draft and implementing it are different steps. The
analyzer should compare the applicable instruction with the actual action and
later recovery. Timestamp order alone does not establish that a queued message
or sibling branch reached a response.

Logs produced on another computer can be reviewed without their generated files.
Their absence on this machine is not evidence that they were never produced.
Admit additional local artifacts explicitly if they are needed, preserving which
version and point in time each snapshot represents.

## Local accounting, browsing and saved reports

From a checkout, accounting works without Claude:

```sh
python3 scripts/ally-session.py --data-dir /absolute/path/private-store run /absolute/path/session.jsonl
```

For a local session browser, choose a directory explicitly:

```sh
python3 scripts/ally-session.py browse /absolute/path/session-directory --detach
```

Opening existing saved results does not require a model call. Starting a new
model analysis in the browser is a separate approved action. For a complete
saved investigation, use [the managed workflow](single-session-usage.md); it
runs an investigation and a separate evidence-review process. HTML, Markdown
and JSON exports preserve saved wording.

The local store persists selected source snapshots, exposure records, immutable
drafts and review history. Keep the same `ALLY_ANALYZER_HOME` for follow-ups.
Keep private logs, stores and reports outside Git. Installing or loading the
plugin does not scan the workstation or analyze sessions automatically.
