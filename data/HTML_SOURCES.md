# HTML Sources — Parse Manifest

> The 10 HTML-only corpus sources (verified live on 2026-08-30, all patient-facing,
> all with visible review dates). Convert to markdown with docling during Phase 1.2.
> Target: `data/parsed/<source>/<filename>` per the layout below.

## Parsing queue (docling HTML → markdown)

| # | Output filename | Source | URL | License | Last reviewed | Categories |
|---|---|---|---|---|---|---|
| 1 | `nidcr_gum_disease.md` | NIDCR/NIH | https://www.nidcr.nih.gov/health-info/gum-disease | Public domain | Aug 2026 | Conditions |
| 2 | `cdc_cavities.md` | CDC | https://www.cdc.gov/oral-health/about/cavities-tooth-decay.html | Public domain | May 2024 | Conditions, Prevention |
| 3 | `nhs_wisdom_tooth_removal.md` | NHS (UK) | https://www.nhs.uk/tests-and-treatments/wisdom-tooth-removal/ | OGL v3.0 | Jun 2024 | Post-procedure, Conditions, Triage |
| 4 | `nhs_root_canal.md` | NHS (UK) | https://www.nhs.uk/tests-and-treatments/root-canal-treatment/ | OGL v3.0 | Oct 2025 | Post-procedure, Conditions |
| 5 | `nhs_tooth_decay.md` | NHS (UK) | https://www.nhs.uk/conditions/tooth-decay/ | OGL v3.0 | Aug 2025 | Conditions, Post-procedure |
| 6 | `nhs_gum_disease.md` | NHS (UK) | https://www.nhs.uk/conditions/gum-disease/ | OGL v3.0 | Apr 2026 | Conditions, Triage |
| 7 | `nhs_teeth_grinding.md` | NHS (UK) | https://www.nhs.uk/symptoms/teeth-grinding/ | OGL v3.0 | Apr 2026 | Conditions |
| 8 | `nhs_dental_abscess.md` | NHS (UK) | https://www.nhs.uk/conditions/dental-abscess/ | OGL v3.0 | Mar 2026 | Triage |
| 9 | `nhs_knocked_out_tooth.md` | NHS (UK) | https://www.nhs.uk/conditions/knocked-out-tooth/ | OGL v3.0 | Feb 2025 | Triage |
| 10 | `nhs_toothache.md` | NHS (UK) | https://www.nhs.uk/symptoms/toothache/ | OGL v3.0 | Jul 2024 | Triage, Conditions |

## Parsing notes (things docling will need handled)

- **Strip boilerplate:** every NHS page carries identical nav/"Support links"/footer
  chrome and a "Page last reviewed / Next review due" block — exclude nav and
  footer from chunks, but **preserve the last-reviewed date** as document metadata
  (it's part of provenance).
- **Preserve the advice-level callouts** ("Urgent advice:", "Immediate action
  required:", "Non-urgent advice:", "Important:") — these blocks are exactly what
  grounds the emergency-triage category and the refusal-boundary golden items.
  Mark them up rather than flattening them into paragraphs.
- **NHS charges/111/999 content:** keep — it's real content — but expect a golden
  set decision on whether NHS-specific service navigation ("call 111") is answer
  material for a likely-US audience (see RESEARCHER_OUTPUT.md assessment).
- **Attribution requirement:** OGL v3.0 requires attribution — the README and
  PROVENANCE must carry "Contains public sector information licensed under the
  Open Government Licence v3.0" for NHS content.

## Category coverage status (from RESEARCHER_OUTPUT.md)

| Category | Status |
|---|---|
| 1. Post-procedure | OK for extraction/wisdom/root canal; **thin for fillings/cleanings** (candidate: nhs.uk dental-treatments page) |
| 2. Conditions | Well covered |
| 3. Prevention | Good; **no dedicated sealants doc** (candidate: CDC sealants FAQ) |
| 4. Emergency triage | Strongest category (5 docs) |
| 5. Insurance glossary | **Weakest** — US general glossary only; no dental-specific terms (annual maximum, missing-tooth clause, etc.). Likely needs an original, clearly-labeled glossary authored by the project. |
