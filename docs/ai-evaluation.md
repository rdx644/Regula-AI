# AI evaluation and responsible use

## Current result

**Not run: 10 intended items, zero real predictions.** OpenAI is the approved provider, but the owner explicitly instructed that evaluation remain unpaid until a budget is supplied. Model execution is off by default. No OpenAI request was made during completion work. Browser extraction uses a disclosed synthetic adapter; its output does not establish model accuracy.

## Reproducible procedure after budget approval

Review the original ten labels before running. Their source page/section labels are not present in the supplied input text. `gold-009` labels an expired valid artifact as `no_evidence`, while the application distinguishes `stale_evidence`. Preserve original labels and record an independently reviewed dataset revision rather than changing expectations to force a pass. A compliance/legal reviewer must confirm suitability and approve the synthetic inputs.

The prediction command remains blocked until approval:

```text
cd backend
python -m evaluation.predict --execute-openai --model gpt-4o-mini --max-requests 20 --max-reserved-tokens 80000 --output ../output/evaluation/predictions.jsonl
python -m evaluation.evaluate --predictions ../output/evaluation/predictions.jsonl
```

The request/token caps are safety bounds, not approved spending. Provider billing limits and managed credentials are also required. A default prediction invocation makes no calls. It refuses to overwrite predictions, records case failures, and counts actual SDK calls including retries. Predictions call the application's extraction and mapping components; gap/risk cases use the actual deterministic services. Queue/persistence and independent retrieval are outside this runner's scope.

Provenance includes dataset SHA256, timestamp, configured and returned model identifiers, prompt version, prompt digest, limits and actual token usage. Never copy expected answers into predictions. Save prediction/provenance/report together, with synthetic data labeling.

## Metrics and acceptance

The evaluator records extraction and primary mapping precision/recall/F1, exact quote/page validity, unsupported citation rate, deterministic gap/risk correctness, case failures and task success. Missing cases and failed predictions cannot pass. An extraction with an invalid citation fails task success even if text matches. Retrieval quality and broader unsupported legal claims remain `not_measured` because independent relevance/claim labels are absent.

Release must require full intended coverage, valid source spans/pages, reviewed labels, no unresolved high-impact unsupported assertions, and defensible quality thresholds agreed with the compliance owner. The governing plan does not supply calibrated numerical thresholds; no arbitrary quality threshold has been promoted into a D2 claim. Ten fixtures are a smoke benchmark, not sufficient statistical evidence of broad banking reliability. Add adversarial, ambiguous, empty and cross-tenant cases before a reliability claim.

## Explicit deterministic assumptions

- Risk score is `round(likelihood * impact * 100, 2)`; zero is preserved. Current levels: critical ≥80, high ≥45, medium ≥20, low otherwise. These are implementation assumptions requiring domain calibration.
- Landscape gap defaults: high finding uses likelihood .8/impact .9; other findings use .5/.6. Reviewed mapping, valid current evidence and a latest passing test with effectiveness ≥.7 are required for a healthy result.
- Historical golden gap fixtures use a disclosed Q3-2024 assessment date, not the current date.
- Scenarios clone a tenant matrix. A baseline row uses .8/.9 when an open gap exists and .2/.3 otherwise. Disabling a control or invalidating evidence uses .8/.9. Multipliers are bounded 0..2; foreign resource IDs are rejected. The result is an assumed comparison, not an authoritative regulatory impact calculation.
- Model-generated evidence/test results stay proposals until an authorized reviewer approves them. A passing reviewed test requires current privately uploaded reviewed evidence. Remediation completion requires a new reviewed passing test after the latest plan change.

Expanding OpenAI prompts with private control/evidence/gap data was rejected by automatic approval review. That expansion was not applied. A separate data-transfer approval and privacy review would be needed before such work, even after a budget is approved.
