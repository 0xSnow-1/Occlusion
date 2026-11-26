# Rerank comparison

## Snapshot

- Snapshot: `evals/guardrails/tasks/live-model-refusal/environment/chunks_v1.jsonl` (120 chunks, sha256 `927616f7eb70d574`)
- Golden set: `data/golden_set_v1.jsonl` (70 answerable items, sha256 `5d32a3270805717a`)
- Top n: 5; relevance gate off; identical snapshot asserted.

## Side by side

| metric | hybrid | hybrid + rerank | delta |
|---|---:|---:|---:|
| recall@5 | 0.985714 | 1.0 | +0.0143 |
| MRR@5 | 0.898095 | 0.909524 | +0.0114 |
| top-1 accuracy | 0.828571 | 0.842857 | +0.0143 |
| hit rate@5 | 0.985714 | 1.0 | +0.0143 |
| p50 latency (ms) | 75.09 | 1329.735 | +1254.6450 |
| p95 latency (ms) | 114.042 | 1822.931 | +1708.8890 |
| mean latency (ms) | 73.901 | 1392.822 | +1318.9210 |

## Ordering movement

- First relevant chunk ranked higher: 8
- Unchanged: 58
- Ranked lower: 4
- Missed in both runs: 0

### Wins

| id | question | off rank | on rank |
|---|---|---|---|
| G01 | How am I supposed to brush my teeth properly? | 5 | 4 |
| G07 | How do I take care of my dentures at night, and should I sleep with them in? | 2 | 1 |
| G09 | What causes dry mouth, and why can it make chewing and talking hard? | 2 | 1 |
| G10 | Can having less spit really lead to cavities? | 3 | 2 |
| G23 | What treatments are used for tooth decay at different stages, and how is it prevented in general? | 2 | 1 |
| G26 | How is gum disease treated at early and serious stages in general? | 2 | 1 |
| G27 | How is gum disease prevented through everyday tooth and gum care? | miss | 4 |
| G67 | What happens step by step during root canal treatment? | 2 | 1 |

### Losses

| id | question | off rank | on rank |
|---|---|---|---|
| G13 | My mouth is often dry - how do I look after my teeth day to day, and when should I get changes checked? | 1 | 3 |
| G18 | How does smoking affect my gums as I age? | 1 | 2 |
| G32 | What is the general guidance for preserving a knocked-out adult tooth before reaching a dentist? | 1 | 2 |
| G33 | Why is a knocked-out baby tooth handled differently from a knocked-out adult tooth? | 1 | 2 |


## Verdict

Keep the rerank stage off by default.

It recovers one missed question (G27) and moves 8 questions up while moving 4 down.
Recall@5 rises 0.9857 to 1.0000 and MRR@5 rises 0.8981 to 0.9095.
That is +0.0143 recall and +0.0114 MRR.
It costs +1254.6 ms at p50 and +1708.9 ms at p95, about 17 times the retrieval time.
The small ordering gain does not earn that latency.

The stage stays implemented and toggleable. Re-evaluate it only if a future change makes cross-encoder scoring much cheaper, or if the golden set grows enough that the ordering gain matters more.
