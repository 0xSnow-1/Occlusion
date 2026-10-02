---
title: Occlusion Dental FAQ
emoji: 🦷
colorFrom: blue
colorTo: green
sdk: gradio
app_file: src/ui/gradio_app.py
pinned: false
license: mit
short_description: Cited dental answers or safe refusal.
---

# Occlusion Dental FAQ

Optional config for pushing the Occlusion demo to a Hugging Face ZeroGPU
(Gradio) Space. Assembled at push time, **not currently deployed** — the live
demo runs on Streamlit Community Cloud (see the repo README).

[Occlusion](https://github.com/0xSnow-1/Occlusion) is a citation-grounded
dental patient-education assistant. Routine questions get answers with
verified sources; diagnostic, prescriptive, or out-of-corpus questions get
safe refusals.

Patient education only — not a diagnostic tool. Always consult a dentist.
Emergency/triage guidance follows NHS UK sources. Contains public sector
information licensed under the Open Government Licence v3.0.
