# Data Provenance

> Every file in `data/raw/` is documented here: what it is, where it came from,
> its license/terms, and when it was accessed. If a source isn't in this table,
> it doesn't go into the corpus.

## Corpus contents — v1 (patient-education, scope-aligned)

### Downloaded files (`data/raw/`)

| File | Source / publisher | Type | Accessed | License / terms | Notes |
|---|---|---|---|---|---|
| `flossing-brushing.pdf` | HRSA (HHS) | PDF | 2026-08-30 | Public domain* | ~6 pp; prevention; *free to duplicate, no resale for fee (42 U.S.C. §1320b-10) |
| `dry-mouth.pdf` | HRSA (HHS) | PDF | 2026-08-30 | Public domain* | ~2 pp; conditions |
| `regular-oral-health-care-keeps-you-healthy.pdf` | HRSA (HHS) | PDF | 2026-08-30 | Public domain* | 1 p; prevention |
| `older-adults-and-oral-health.pdf` | NIDCR/NIH | PDF | 2026-08-30 | Public domain | 6 pp, Nov 2023; conditions incl. oral-cancer warning signs |

### HTML-only pages (to be parsed via docling — see `HTML_SOURCES.md` for manifest)

| Source | Pages | License | Verified live |
|---|---|---|---|
| NIDCR/NIH | 1 (gum disease) | Public domain | 2026-08-30 |
| CDC | 1 (cavities) | Public domain | 2026-08-30 |
| NHS (UK) | 9 (wisdom tooth removal, root canal, tooth decay, gum disease, teeth grinding, dental abscess, knocked-out tooth, toothache, dental treatments) | OGL v3.0 ("© Crown copyright" on every page) | 2026-08-30 |

**OGL attribution requirement:** NHS-derived content requires the notice
"Contains public sector information licensed under the Open Government Licence
v3.0" — carry this in the README.

**Rejected sourcing (do not re-research):** MedlinePlus `/ency/` pages
(A.D.A.M./Ebix copyright, AI/RAG use explicitly prohibited), ADA MouthHealthy /
Colgate / WebMD (all rights reserved), NADP dental glossary (no open license),
individual NHS Trust leaflets (per-Trust copyright, not covered by nhs.uk OGL).
Full rationale: `RESEARCHER_OUTPUT.md`.

## Archived corpus (v1 → v2 decisions)

The following were **archived to `data/raw/_archive/`** (gitignored — not
redistributed):

- **9 clinical-guideline files** (AAPD, AAP staging, AHA/ADA prophylaxis, dosage
  charts, etc.): v1 scope (SCOPE.md §4) calls for patient-education material;
  clinical guidelines and dosage charts fight the patient-FAQ framing and muddy
  the refusal boundary. Retained locally as a **v2 "clinician-mode corpus"**
  candidate — see SCOPE.md §9.
- **CMS Uniform Glossary of Health Coverage** (`Uniform-Glossary-01-2020.pdf`):
  insurance terminology was **descoped for v1** (SCOPE.md §5) — the glossary covers
  general medical coverage, not dental benefits, so keeping it in the corpus would
  make retrieval answer "what's a deductible" and fight the refusal boundary.
  A "what's a deductible"-style question is now a golden-set `refuse_no_coverage`
  item. Revisit in v2 with an original, clearly-labeled glossary.

## What is deliberately NOT in the corpus

*TODO: list the topics/sources you chose to exclude and why (scope alignment with
SCOPE.md §4–5).*

## Known gaps / currency

*TODO: how current is this material? Any guideline updates expected? Any topics
patients ask about that this corpus cannot answer? (These become your
`refuse_no_coverage` golden-set items.)*
