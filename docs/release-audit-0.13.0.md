# 0.13.0 — Developer reading flow

October 15, 2026. This is a product and implementation audit, not a revision of Claude's saved findings. Changes are committed locally in focused commits. No remote was added or pushed.

## Delivered behavior

- The opening links to not-met and unverified requirements and unresolved/unknown findings. Those are distinct states; a historical procedural omission does not automatically become a repair task. A next check appears only when Claude saved one.
- Requirement rows show the saved obligation, status and result/check basis. The complete wording, intent changes, scope, verification, artifact revision and gaps remain in the expanded row. Map-level review qualifications are labelled once at map scope, not presented as separate judgments on every requirement.
- Finding links use saved titles. Source links use saved explanations when available. Literal previews do not introduce another model summarization step.
- All main turns remain in chronological order. Focus controls select explicit evidence identities and keep an All turns control. Opening an out-of-selection source restores its context.
- Saved recovery attempts form a connected sequence. Direct comparison exposes tool inputs, changed input fields, linked results and saved verification scope/revision. Different or multi-tool inputs are not automatically aligned. Associated resource details retain every token component and timing distinction.
- Copy remaining work assembles inspectable saved text, scopes, checks, optional actions, limits, capture gaps, record reviews and source identities. It generates no new prompt and applies no change. An absent next action stays absent.
- Qualified review assessments can collapse; their verdicts and uncertainties remain visible. Needs-revision assessments stay visible. Source selection and report position survive inspector collapse/reopen.
- Library HTML export uses the current renderer over the immutable saved JSON. Original HTML files are retained; JSON downloads preserve the saved bytes.

The governing spec, system explanation, Mermaid diagram and investigation/review/writing skills were updated. The plugin retains the standard manifest, Markdown skills and packaged Python/scripts layout.

## Mechanical validation

The final suite discovered 247 tests in 23.701 s: 245 passed and two optional private-corpus tests were skipped. The complete output is retained at `.analysis/developer-flow/backend-final.log`. New regressions cover full chronology, descriptive labels without payload edits, separate not-met/unverified states, no invented action after recovery, explicit evidence-based turn selection, preserved review dissent and scope, optional next-action admission, ambiguous intent prerequisites, and recovery scope/resource presentation. The existing stale-check, narrower-retry, expected-failure, denial, child-overlap, token, disclosure, instruction-admission and library tests remain in the suite.

The installed Claude manifest validator passed. Its marketplace-install suggestion is advisory; no marketplace or remote repository is configured. Packaging tests exercise clean extraction and MCP entry points. The distributable ZIP contains 91 allowlisted files, excluding private source stores and model-run artifacts. JavaScript syntax validation passed. These checks establish tested behavior, not semantic accuracy.

## Browser observations

Checked the supplied migration report, actual native CSV/TTLCache development reports, and an earlier completed Claude investigation of the clearly labelled synthetic red/green fixture. Historical report prose was not edited.

- Migration: 32 visible chronological rows; the open-evidence filter selected six explicitly related turns; All turns restored 32. Descriptive finding links opened the saved finding and review qualification.
- Requirements: compact rows expanded into full intent/result/revision/check evidence. The native TTLCache report retained four requirements, including one not met and one unverified; no status was inferred from the Ready freshness label.
- Recovery: original and verification commands appeared together. Selecting an Edit attempt instead produced an explicit incomparable-input notice. Linked results opened the source inspector. The same source ID survived collapse/reopen.
- Copy: the final native TTLCache handoff copied all 6,254 characters exactly, including one map-level review. The earlier synthetic handoff and verification-command copies also matched. The in-app browser's initially empty clipboard read was a test-driver state issue while an unused blank tab was active. After closing it, the documented clipboard API confirmed the bytes. No alternative clipboard or browser-control technology was used.
- Export: browser-downloaded JSON matched the saved report bytes. HTML matched the current standard renderer and embedded an unchanged report payload. Final receipt: `.analysis/developer-flow/export-check-final.json`. A second download initially timed out because the first download had closed the export menu; reopening the menu completed it.
- Narrow layout: at 390 × 844, source inspection used a 390-pixel modal and retained its selected identity. The report had no outer horizontal overflow. Comparison columns stacked into one 342-pixel column. Exact source/input copying, original text and full-result access remain available.

Screenshots and private browser receipts are retained in `.analysis/developer-flow/`. `11-final-comparison-desktop.png`, `13-final-comparison-narrow-inputs.png`, and `09-narrow-source-verified.png` show the completed recovery/source layouts. `15-final-native-outcome.png` and `16-final-requirement-review.png` show the scoped review label and original assessment; `17-final-native-narrow.png` captures the final native report at 390 × 844. Screenshots are not an accessibility certification; the checks exercised keyboard activation and labelled controls, not every assistive-technology combination.

## Fresh Claude behavior: interrupted, not passed

Two approved managed investigations used frozen source commit `65c371e` with `investigate-v15`, `review-v7`, `write-report-v10`, requirement policy v3 and semantic-consistency policy v2. Their package manifest still identified the pre-release snapshot as 0.12.1; the final presentation/package is 0.13.0. The default unanchored question and controlled-excerpt readers were used. Each started a separate review host, then hit the account session limit. Both runs stopped with `failed`, retained the host's actual reason and saved no final reviewed conclusion. No further model retry was made.

| Input | Observed run | What it establishes |
| --- | --- | --- |
| Saved native CSV coding session on a development task | `investigation_052288cf0bfe466e89aa8ff388fd6dd4`; 202.34 s observed analyzer span; $1.126977 host-reported list cost | New tools/skills loaded and a draft map/finding was saved. Review did not complete. |
| Authored synthetic diagnostic trace with a narrowed retry, later edit and missing verifier | `investigation_8c0a1df322974224b22b19c320b69085`; 197.42 s; $1.0970014 host-reported list cost | Claude saved the final revision as unverified and authored an optional next action with command, sources, verification and a repository-state limit. Review did not complete. |

Transport audits report scoped tools only and equality between saved model records and Claude's submitted tool inputs. All drafts and host streams remain in `.analysis/developer-flow/claude-csv/` and `claude-recovery/`. Codex did not repair or polish their prose. No new skill recommendation was manufactured.

The CSV draft still contains material errors: it says no first-turn report text was captured, although source `ev_bd9bf758d57366ae185a9421` contains that report. It also marks bundled work completed while retaining an unverified constraint. Its inventory does not establish that all material intent was identified. These are unreviewed draft problems, not proof that the final review would have accepted them; neither are they a passed diagnostic-quality test.

The earlier completed CSV report still overstates the disputed reading-order interpretation. Re-rendering preserves that historical judgment. The new contract can reject a **declared** ambiguity paired with a confident verdict; it cannot reliably discover all ambiguous intent or force Claude to identify every missing obligation. A successful, separately reviewed rerun remains needed after the host limit resets.

## Remaining limitations

1. Complete the interrupted model-behavior checks, especially competing intent interpretations and whether the reviewer repairs unsupported completion claims. Do not silently replace the current completed report with an unfinished draft.
2. Run the existing independent evaluation on unseen sessions before claiming better diagnostic usefulness than `/insights`. These development examples are not held-out evidence, and the tool is not certified slop-free.
3. Historical incidents without a saved episode cannot acquire a connected recovery judgment through rendering alone. Historical sources without explanations keep neutral fallback labels. Producing those fields requires another Claude investigation.
4. Explicit evidence focus is navigation, not an importance ranking or a complete task inventory. Long saved titles can remain unwieldy; full text is retained rather than rewritten.
5. Ally schemas, authentication, historical plugin versions and private child traces remain deferred. No speculative connector, active-time estimate, cost-saving claim or cross-session score was added.
