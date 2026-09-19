# Deployment research findings (2026-09-19, live primary-source research)

Researcher ran this against current provider docs and pricing pages, checked 2026-09-19, rather than from memory.

## Part 1 — Ranked options

| Host | Billing needed | RAM ceiling | Sleep/expiry | Effort | Demo quality | Verdict |
|---|---|---|---|---|---|---|
| Streamlit Community Cloud | No, GitHub OAuth only, no card anywhere in the flow | 690MB to 2.7GB per app, per Streamlit's own docs (docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app, checked 2026-09-19; the page's own as-of date is Feb 2024, still the live number) | Hibernates after 12h with no traffic, wakes on next visit. Exact wake duration is not published. Community reports mostly land under a minute for a warm build, but this is UNVERIFIED as a hard number | Low, native Streamlit UI already exists at `src/ui/app.py`, no Dockerfile, no CLI | Good, contingent on fitting the RAM ceiling | Winner, with a caveat, stated runtime RAM of roughly 2 to 4GB can exceed 2.7GB, needs the Task B trim |
| Railway | No card for the 30-day and $5 trial, reverts to a $1 per month credit Free plan after | 0.5 to 1GB (railway.com/pricing, checked 2026-09-19) | Trial expires in 30 days, not a recurring free host | — | — | Killed: not persistent, and too little RAM even during the trial |
| Koyeb | No card for Hobby plan (koyeb.com/pricing FAQ, checked 2026-09-19) | 512MB | Does not sleep, but RAM is the wall | — | — | Killed: RAM |
| Render | No card (render.com/docs/free, checked 2026-09-19) | 512MB (Free instance type) | Spins down after 15 min idle, roughly 1 min wake | — | — | Killed: RAM |
| Oracle Cloud Always Free | Card required for identity verification, even though it is always free (oracle.com/cloud/free FAQ, checked 2026-09-19) | 24GB (Ampere A1) | — | — | — | Killed: billing (refundable holds count as billing) |
| Google Cloud Run | Billing account required to attach, even inside free grant | — | — | — | — | Already tried and killed, no dated change found |
| Modal | $1 usable without a card, rest locked behind one | — | — | — | — | Already tried and killed, no dated change found |
| Fly.io | No free tier for new signups as of 2026, card required | — | — | — | — | Killed: billing |
| GitHub Codespaces | No card, 120 core-hours per month free | 2-core and 4GB typical | Idle timeout stops the instance, the public-port URL goes dead until manual restart | — | — | Killed: not clickable anytime, fails the recruiter-no-friction test |
| Replit | No card for Starter | Roughly 2GiB compute (per Replit's own 2026 pricing writeups) | Published free apps go offline after 30 days without a paid Core plan, plus a Made with Replit badge | — | — | Killed: not actually always-on for free |
| PythonAnywhere (Beginner) | No card | 512MB disk, 100 CPU-seconds per day, 3GB per-process cap but restricted outbound internet (help.pythonanywhere.com, checked 2026-09-19) | App expires after 1 month unless manually renewed | — | — | Killed: restricted outbound internet blocks Bedrock calls, plus the CPU budget is too small |
| Back4app Containers | No card (back4app.com/pricing, checked 2026-09-19) | 256MB | 600 free hours per month | — | — | Killed: RAM |
| HF Docker and Gradio SDK, CPU | PRO paywall (already tried) | — | — | — | — | Reconfirmed still true, a dated Sept 2026 HF community-forum complaint thread confirms the CPU Basic Docker and Gradio SDKs are still paywalled for free accounts |
| HF ZeroGPU | Free, but architecture mismatch (already tried) | — | — | — | — | Killed: fits GPU-bound request functions, not a persistent CPU chat server, unchanged |
| HF Community Grant | Free | — | — | — | — | Killed: grants only raise hardware tier on an existing Space (for example CPU to T4), they do not unlock the Docker or Gradio SDK paywall itself |
| Vercel and Cloudflare Workers | No card | Function-size and CPU-time limits (5 min and 10ms CPU respectively) | — | — | — | Killed: no path to run torch plus sentence-transformers plus local Qdrant as a persistent process |
| Azure for Students | No card, but requires verified full-time accredited-university enrollment | Enough for a small App Service | $100 credit per year, renewable while enrolled. This is a credit, not a recurring $0 tier | Medium (Azure App Service setup) | Good if eligible | Conditional fallback, only with current student status. Flagged separately per the rule against confusing credits with free tiers |
| AWS Educate Starter Account | No card, third-party (Vocareum) managed | Capped, service-list-restricted | $25 to $100 per year credit depending on institution | Higher (raw EC2, not PaaS) | Fair | Lower priority than Azure for Students. More DevOps work, and current 2026 program status is UNVERIFIED |
| Zeabur | $5 free credit per month, not a $0 tier | 512MB | — | — | — | Deprioritized and UNVERIFIED. Credit-based, not confirmed card-free |

## Part 2 — Slim-down analysis (Task B, researcher version)

Researcher believed runtime RAM came from loading torch plus sentence-transformers alongside fastembed, and proposed dropping them for fastembed-only embedding with a Ragas re-run to confirm nothing moved.

## Part 3 — Strategic verdict (researcher version)

Researcher flagged circulating portfolio-hiring statistics (specific percentages, named studies) as UNVERIFIED, likely SEO-generated, and unable to trace to real methodology.
What holds up across named-source writeups is qualitative: a live clickable demo differentiates from notebook-only applicants, but for junior roles it is a differentiator, not a gate. README and methodology clarity plus interview trade-off talk do the gatekeeping.
Ranking by hiring impact: README and methodology clarity roughly equal to live deployment (when cheap), then demo recording, then one-command reproducibility, then eval-numbers writeup (eval numbers matter as README content, not as a separate artifact).
Verdict: deploy-first, because Streamlit Community Cloud makes a live link nearly free given the existing UI. Strongest reason: a link the reader does not have to press play on converts attention faster than a video.

## Part 4 — Deploy-first steps (researcher version, superseded in detail by maintainer verification below)

Researcher steps: vendor the Qdrant index with `git add -f`, remove torch plus sentence-transformers, re-run pytest plus the Ragas eval, push `main`, then share.streamlit.io flow (GitHub sign-in, repo, branch, `src/ui/app.py`, Python 3.12, TOML secrets, deploy, watch resource usage).

## Maintainer verification (2026-09-19, same day)

- Streamlit resource numbers CONFIRMED against the live primary source (`docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app`, page copyright 2026): CPU 0.078 to 2 cores, memory 690MB to 2.7GB, storage 50GB max, hibernation after 12h without traffic with wake by any visitor. The page's numbers carry a Feb 2024 as-of date but remain the published limits.
- Task B is better than the researcher thought: `rg` over `src/`, `tests/`, and `scripts/` finds ZERO imports of torch or sentence-transformers. Dense and sparse embeddings are 100 percent fastembed via the qdrant-client integration. `sentence-transformers` sits in `pyproject.toml` as an unused direct dep and torch exists only transitively in `uv.lock`. Removing the dep changes zero vectors, so NO golden-set or Ragas re-run is required. The re-run warning in Part 2 does not apply.
- Remaining deltas before deploy: remove the dep plus re-lock (needs owner approval per repo rule), add a `requirements.txt` (Community Cloud installs from it, not from `pyproject.toml`), force-add the 1.4 MB index, set TOML secrets in-app settings, deploy from `main`.
