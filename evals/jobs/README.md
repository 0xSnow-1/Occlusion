# evals/jobs — Harbor run records

Only canonical run directories are committed here. Everything present is cited
by the README or by the eval task specs / occlusion skill:

- `2026-09-08__03-02-25` — trap-refusal, scaled audit, 73/73 (README).
- `2026-09-08__03-02-55` — boundary-precision, scaled audit, 53/53 (README).
- `2026-09-08__03-03-25` — nearmiss-refusal, scaled audit, 78/78 (README).
- `2026-09-08__07-51-31` — live-model-refusal oracle, 192/202 (Task.md, SKILL.md).
- `2026-09-07__23-34-56` — first Task-1 oracle run, reward 1.0 (SKILL.md).
- `2026-09-08__01-28-16`, `2026-09-08__02-18-04` — pre-scale oracle runs of
  boundary-precision and nearmiss-refusal, reward 1.0, superseded by the scaled
  audits above.
- `2026-09-08__06-52-38`, `2026-09-08__07-44-29` — documented-INVALID
  live-model runs (`NoCredentialsError`; reward 0), kept as the evidence
  behind the Harbor secret lesson in the occlusion skill.

Aborted/errored setup runs (`2026-09-07__23-31-04`, `2026-09-07__23-32-39`) were
removed. Generated `result.json` files keep the original build-machine path in
their `trial_uri` fields; these are machine-generated artifacts, not repo text,
and are left untouched.