I'll research this systematically across the preferred government/NHS sources, verifying licenses and direct download links as I go.Important finding: MedlinePlus A.D.A.M. Medical Encyclopedia content (the `/ency/` pages, which is where extraction/root canal/dry-socket aftercare articles live) is explicitly copyrighted by Ebix/A.D.A.M. and its terms **explicitly prohibit use in AI/RAG training and redistribution**. I'll exclude all `/ency/` MedlinePlus pages and pivot to NHS UK for post-procedure and emergency-triage content, which is OGL-licensed.# Dental Health FAQ Corpus — Research Findings

I focused on NIDCR, HRSA, CDC, and NHS (nhs.uk) as primary sources, and made one important discovery that changes the sourcing strategy: **MedlinePlus's `/ency/` Medical Encyclopedia pages (the ones covering "Tooth extraction," "Dry socket," "Root canal treatment," etc.) are licensed from A.D.A.M./Ebix, not public domain — and their terms explicitly prohibit use in AI training or retrieval systems.** I excluded all of these and pivoted to NHS UK (OGL v3.0, confirmed via nhs.uk's own terms page and the "© Crown copyright" footer on every page I fetched) to cover post-procedure and emergency-triage content instead. Every URL below was fetched directly and confirmed to resolve.

## Quick-scan summary

| # | Title | Publisher | Format | License | Last Updated |
|---|---|---|---|---|---|
| 1 | Oral Health Info for Adults: Flossing and Brushing | HRSA (HHS) | PDF | Public domain* | Jan 2023 |
| 2 | Oral Health Info for Adults: Dry Mouth | HRSA (HHS) | PDF | Public domain* | Jan 2023 |
| 3 | Regular Oral Health Care Keeps You Healthy | HRSA (HHS) | PDF | Public domain* | Jan 2023 |
| 4 | Older Adults and Oral Health (Myths & Facts) | NIDCR/NIH | PDF | Public domain | Nov 2023 |
| 5 | Uniform Glossary of Health Coverage & Medical Terms | CMS/HHS/DOL | PDF | Public domain | 2020 (current) |
| 6 | Periodontal (Gum) Disease | NIDCR/NIH | HTML | Public domain | Aug 2026 |
| 7 | About Cavities (Tooth Decay) | CDC | HTML | Public domain | May 2024 |
| 8 | Wisdom Tooth Removal | NHS (UK) | HTML | OGL v3.0 | Jun 2024 |
| 9 | Root Canal Treatment | NHS (UK) | HTML | OGL v3.0 | Oct 2025 |
| 10 | Tooth Decay | NHS (UK) | HTML | OGL v3.0 | Aug 2025 |
| 11 | Gum Disease | NHS (UK) | HTML | OGL v3.0 | Apr 2026 |
| 12 | Teeth Grinding (Bruxism) | NHS (UK) | HTML | OGL v3.0 | Apr 2026 |
| 13 | Dental Abscess | NHS (UK) | HTML | OGL v3.0 | Mar 2026 |
| 14 | Knocked-Out Tooth | NHS (UK) | HTML | OGL v3.0 | Feb 2025 |
| 15 | Toothache | NHS (UK) | HTML | OGL v3.0 | Jul 2024 |

*HRSA docs: explicitly "not copyrighted, free to duplicate and use," but under 42 U.S.C. §1320b-10 may not be **resold for a fee** — fine for a public repo, not for a paid product built directly on the PDF images.

---

## Full details

**1. Oral Health Information for Adults: Flossing and Brushing**
Direct PDF: https://www.hrsa.gov/sites/default/files/hrsa/oral-health/flossing-brushing.pdf
~6 pages | Categories: **Preventive care (3)**, touches **Post-procedure (1)** via denture care
Example questions: "What's the correct flossing technique?" / "What toothbrush should I use?" / "Do I need to floss around a bridge or crown?"

**2. Oral Health Information for Adults: Dry Mouth**
Direct PDF: https://www.hrsa.gov/sites/default/files/hrsa/oral-health/dry-mouth.pdf
~2 pages | Category: **Common conditions (2)**
Example questions: "Why is my mouth always dry?" / "Is dry mouth just part of aging?" / "What can I do about medication-related dry mouth?"

**3. Regular Oral Health Care Keeps You Healthy**
Direct PDF: https://www.hrsa.gov/sites/default/files/hrsa/oral-health/regular-oral-health-care-keeps-you-healthy.pdf
1 page | Categories: **Preventive care (3)**, **Post-procedure (1)**
Example questions: "Why do I need check-ups if nothing hurts?" / "What's the point of a professional cleaning?" / "How often should I see a dentist?"

**4. Older Adults and Oral Health: Myths and Facts**
Direct PDF: https://www.nidcr.nih.gov/sites/default/files/2023-12/older-adults-and-oral-health.pdf
6 pages | Category: **Common conditions (2)** — cavities, gingivitis vs. periodontitis, dry mouth, oral cancer warning signs
Example questions: "What's the actual difference between gingivitis and periodontitis?" / "Can a tooth with a filling still get a new cavity?" / "What mouth symptoms mean I should get checked for oral cancer?"

**5. Uniform Glossary of Health Coverage and Medical Terms**
Direct PDF: https://www.cms.gov/cciio/resources/forms-reports-and-other-resources/downloads/uniform-glossary-01-2020.pdf
6 pages | Category: **Insurance glossary (5)**
Example questions: "What's the difference between a copay and coinsurance?" / "What does UCR mean on my dental bill?" / "What is preauthorization?"

**6. Periodontal (Gum) Disease**
https://www.nidcr.nih.gov/health-info/gum-disease (HTML-only)
Category: **Common conditions (2)**
Example questions: "What actually causes gum disease?" / "How do dentists diagnose periodontitis?" / "Can gum disease be reversed?"

**7. About Cavities (Tooth Decay)**
https://www.cdc.gov/oral-health/about/cavities-tooth-decay.html (HTML-only)
Categories: **Common conditions (2)**, **Preventive care (3)**
Example questions: "Can a cavity exist without pain?" / "Does every cavity need a filling?" / "Am I going to lose my teeth eventually anyway?"

**8. Wisdom Tooth Removal**
https://www.nhs.uk/tests-and-treatments/wisdom-tooth-removal/ (HTML-only)
Categories: **Post-procedure (1)**, **Conditions (2)**, **Emergency triage (4)**
Example questions: "Is a week of swelling after wisdom tooth removal normal?" / "How do I know if I have dry socket?" / "When should I worry after having a wisdom tooth out?"

**9. Root Canal Treatment**
https://www.nhs.uk/tests-and-treatments/root-canal-treatment/ (HTML-only)
Categories: **Post-procedure (1)**, **Conditions (2)**
Example questions: "Is numbness after a root canal normal?" / "How long should soreness last?" / "Why do I need a crown afterward?"

**10. Tooth Decay**
https://www.nhs.uk/conditions/tooth-decay/ (HTML-only)
Categories: **Conditions (2)**, **Post-procedure (1)**
Example questions: "What are the first signs of a cavity?" / "Will this need a filling or a root canal?" / "How do I stop a cavity from getting worse?"

**11. Gum Disease**
https://www.nhs.uk/conditions/gum-disease/ (HTML-only)
Categories: **Conditions (2)**, **Emergency triage (4)**
Example questions: "My gums bleed when I brush — is that serious?" / "When does gum disease become an emergency?" / "How is gum disease treated?"

**12. Teeth Grinding (Bruxism)**
https://www.nhs.uk/symptoms/teeth-grinding/ (HTML-only)
Category: **Conditions (2)**
Example questions: "Why do I grind my teeth at night?" / "Is a nightguard the only treatment?" / "Can stress really damage teeth?"

**13. Dental Abscess**
https://www.nhs.uk/conditions/dental-abscess/ (HTML-only)
Category: **Emergency triage (4)**
Example questions: "I have a swollen, painful gum — is this an emergency?" / "Should I go to the ER or wait for a dentist?" / "What can I do for abscess pain while I wait?"

**14. Knocked-Out Tooth**
https://www.nhs.uk/conditions/knocked-out-tooth/ (HTML-only)
Category: **Emergency triage (4)**
Example questions: "My kid's tooth got knocked out — should I put it back in?" / "How do I store a knocked-out tooth on the way to the dentist?" / "Can an adult tooth that got knocked out be saved?"

**15. Toothache**
https://www.nhs.uk/symptoms/toothache/ (HTML-only)
Categories: **Emergency triage (4)**, **Conditions (2)**
Example questions: "How long should I wait before seeing a dentist about tooth pain?" / "When does tooth pain mean I should go to the ER instead?" / "What can I do to ease a toothache tonight?"

---

## Category coverage assessment

- **Category 4 (emergency triage)** is now your strongest category (5 documents with explicit "urgent/non-urgent/999" language) — this is the one place NHS content is unambiguously better than anything U.S. federal sites publish for patients.
- **Category 2 (conditions)** is well covered — cavities, gingivitis/periodontitis, dry mouth, bruxism, wisdom teeth.
- **Category 1 (post-procedure)** is solid for extraction/wisdom-teeth and root canal, but **thin for routine fillings and cleanings specifically** — I couldn't find a public-domain/OGL patient page dedicated to "what's normal after a filling" or "after a scale and polish." Consider adding `nhs.uk/live-well/healthy-teeth-and-gums/dental-treatments/` (also OGL, describes what happens during fillings/scale-and-polish, though it's a "what is this treatment" page rather than aftercare-specific).
- **Category 3 (preventive)** covers brushing/flossing/checkups/fluoride well but has **no dedicated sealants document** and diet guidance is only embedded in passing. Consider adding CDC's `cdc.gov/oral-health/php/school-dental-sealant-programs/index.html` or the sealants FAQ referenced from it.
- **Category 5 (insurance glossary)** has only one document, and it's a *general* health-insurance glossary — it covers deductible/copay/coinsurance/UCR/preauthorization well, but **doesn't define dental-specific terms** like "annual maximum," "missing-tooth clause," "predetermination," or "waiting period." I could not find a public-domain or clearly-licensed source for these dental-specific terms (see rejected NADP glossary below). This is the weakest category — you may need to draft a short original glossary for these terms rather than sourcing one.

---

## Rejected sources (so you don't re-research them)

| Source | Reason for rejection |
|---|---|
| **MedlinePlus `/ency/` pages** (Tooth extraction, Dry socket, Root canal treatment, etc.) | Copyrighted by A.D.A.M./Ebix, not NLM public domain. Terms explicitly state: *"Use of any content for training... AI systems... retrieval-augmented systems... is prohibited without express written consent."* Direct conflict with your use case. |
| **ADA MouthHealthy, Colgate, WebMD, Oral-B, Medical News Today** | Commercial content, all rights reserved, no redistribution license found — excluded per your own hard constraint. |
| **NADP "Glossary of Dental Insurance Terms" PDF** (nadp.org) | Freely downloadable ≠ freely redistributable. It's a trade-association document with no visible open license; likely all-rights-reserved despite public URL. This is the one place I found dental-specific benefit vocabulary (annual maximum, predetermination, missing-tooth clause) — you'd need to contact NADP for explicit permission or write original definitions instead. |
| **Individual NHS Trust patient leaflets** (e.g., Royal Devon, Leeds Teaching Hospitals, Guy's & St Thomas', Bedfordshire Hospitals wisdom-teeth/root-canal PDFs) | Each Trust publishes under its own copyright notice, not automatically covered by the national OGL blanket that applies to the flagship nhs.uk domain. Licensing would need per-Trust verification. I stuck to nhs.uk itself, which has a clear, confirmed OGL v3.0 statement. |
| **MedlinePlus health-topic overview pages** (e.g., medlineplus.gov/dentalhealth.html) | Not rejected on license grounds, just low-value: these are mostly link directories to other orgs' sites with very little original NLM-authored content to ground answers on. |
| **NIDCR "Oral Health in America" report / CDC Oral Health Surveillance Report** | Audience mismatch — these are academic/clinical-statistics reports, not written at patient reading level. |

## Recency note

Everything in the final 15 was verified current: the HRSA and NIDCR PDFs date to late 2023, and every NHS page carries a visible "Page last reviewed" date, with several reviewed in 2025–2026 (Root Canal: Oct 2025; Gum Disease: Apr 2026; Teeth Grinding: Apr 2026; Dental Abscess: Mar 2026). The CMS Uniform Glossary PDF itself is dated 2020, but it remains the current official version linked from cms.gov's live page (checked 2026) — the terminology it defines (deductible, copay, UCR) is stable and not time-sensitive.
