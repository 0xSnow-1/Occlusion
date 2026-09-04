# Universal Stack — drop-in AGENTS.md

Copy this file as `AGENTS.md` into any project.
It is project-agnostic: no project names, paths, or corpus details below.
Keep a `STACK.md` next to it as the source of truth; this file is the inlined fallback.

## Known stack

- Runtime: Python 3.12+, `uv`, `python-dotenv`.
- Orchestration: LangGraph (preferred for stateful agents); `langgraph-supervisor` / `langgraph-checkpoint-postgres` only when needed; `langchain-core` + `langchain-community` as companions.
- Retrieval: Qdrant (`qdrant-client[fastembed]`), `fastembed` (local dense + sparse), `sentence-transformers`; `langchain-qdrant`, `langchain-huggingface` for integrations.
- LLM providers (pick one generation path per project): `langchain-openai`, `langchain-aws` + `anthropic[bedrock]` + `boto3`, `langchain-groq`, `langchain-google-genai`.
- Eval / observability: `ragas` + `pytest`, LangSmith tracing via env keys.
- Backend: Pydantic v2 for all structured output; `fastapi` + `uvicorn` only when a service is needed; `psycopg[binary]` + `psycopg-pool` only with Postgres checkpointing.
- Parsing: `pymupdf`, `pypdf`, `docling[chunking]`.
- Dev: `pytest`, `ipython`.

## Rules for agents

- Prefer the simplest solution using a library already listed above over adding a new dependency.
- A new dependency needs the user's explicit approval first.
- If the project requires something new: research 1–2 candidates, explain why in layman's terms, go through the learning process with the user, then record the winner in `STACK.md` so future sessions can use it.
- Never introduce a dependency the user has explicitly excluded without asking first.
