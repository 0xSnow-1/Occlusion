# Retrieval Relevance Gate

**Date:** 2026-10-24
**Status:** Accepted
**File:** `src/retrieve/relevance.py`

## Decision

Gate the hybrid retriever on raw dense and sparse top-1 scores before generation.
A question is relevant when at least one signal clears its floor:

- dense cosine >= `0.35`, or
- sparse SPLADE >= `10.0`.

Descoped insurance terminology is refused before any embedding call.
`make_retriever` returns an empty list when the gate refuses, so the existing graph path fails closed with `Refusal(insufficient_context)` and the LLM never runs.

## Why

- A neutral off-corpus question still retrieves plausible dental chunks, so the model was the only refusal layer.
- RRF scores are rank-based and have no similarity scale.
  A threshold on a fused score would be arbitrary and would pass a single irrelevant chunk that ranks first in both lists.
- Raw dense and sparse scores have stable, different scales.
  Dense handles paraphrase; sparse handles exact terminology.
  An OR rule keeps exact-term recall without letting a weak dense match force an answer.
- Insurance questions look dental to both retrievers.
  The score gate cannot catch "Does my dental plan cover a root canal?" because it scores higher than many answerable items.
  SCOPE.md §5 already descopes insurance for v1, so a narrow deterministic rule is the correct layer.

## Evidence

Measured on the 133-point demo index with `scripts/measure_relevance_gate.py`:

| Signal | Lowest answerable golden item | Highest pure off-topic item |
|---|---:|---:|
| Dense cosine | 0.447 | 0.316 |
| Sparse SPLADE | 12.74 | 7.82 |

Key refusal examples:

| Item | Dense | Sparse | Gate reason |
|---|---:|---:|---|
| "What is the capital of France?" | 0.124 | 4.46 | `low_similarity` |
| "What's my dental insurance deductible?" | 0.484 | 10.73 | `descoped_topic` |
| "Does my dental plan cover a root canal?" | 0.590 | 26.17 | `descoped_topic` |

Result: 0 false accepts and 0 false refusals across 72 gate-scored golden items plus 12 negative items.
The 6 diagnostic trap items are excluded because the pre-LLM guardrail owns those.

## Tradeoffs

- The hybrid path now runs two extra top-1 searches before fusion.
  This is acceptable for the MVP and can move to `query_batch_points` later if latency matters.
- The insurance regex is deliberately narrow.
  It covers insurance, deductible, premium, copay, reimbursement, claim, dental/health/medical plan, and plan/policy cover or pay.
  Other descoped topics still rely on the model refusal path until they get the same treatment.
- The gate is conservative: a question with a weak dense score but a strong exact-term sparse score still passes.
  This biases toward answering covered questions and uses the model's own refusal as the second layer.

## Alternatives rejected

- **Threshold the RRF score.** Rejected because RRF is rank-based, not a similarity measure.
- **Dense-only threshold.** Rejected because exact terminology questions can have low dense similarity.
- **Bare insurance keyword blocklist in the guardrail.** Rejected because the guardrail's contract is decision-shaped scope rules, and a retrieval-coverage refusal has a different reason (`insufficient_context`).

## Reproduce

```bash
uv run python scripts/measure_relevance_gate.py
```

The script exits nonzero on any false accept or false refusal.
