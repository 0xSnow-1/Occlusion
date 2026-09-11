"""CLI entry point for the dental RAG agent (TODO Phase 5.3 end-to-end).

Wires the real stack together, mirroring the Haiku pattern from
grounded_clinical_agent (Bedrock, temperature=0 for grounded output):

    repo-local Qdrant (data/qdrant_storage) -> hybrid retriever (dense+sparse, RRF)
    -> Claude Haiku 4.5 via Bedrock @ temperature 0
    -> build_graph (retrieve -> generate -> verify -> decide, fail closed)

Usage:
    uv run python scripts/run_agent.py --chat        # interactive: you type questions, watch nodes stream
    uv run python scripts/run_agent.py "Does flossing really help?"
    uv run python scripts/run_agent.py                # 3 demo questions

Requires the collection to exist first: `uv run python scripts/run_ingest.py`.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from langchain_aws import ChatBedrockConverse  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402

from src.agent.graph import build_graph  # noqa: E402
from src.ingest.vector_store import VectorStore  # noqa: E402
from src.retrieve import make_retriever  # noqa: E402

logger = logging.getLogger("run_agent")

COLLECTION_NAME = "occlusion"

# Same model family/ID convention as grounded_clinical_agent / Multi-agent
# repo: global cross-region inference profile for claude-haiku-4.5.
BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0"
)
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")

# temperature=0: RAG answers must be grounded and reproducible; sampling
# creativity has no place on the medical path (trap-question refusals are
# the ship gate). AWS_BEARER_TOKEN_BEDROCK is picked up from the
# environment by the boto3 credential chain — never hardcode it.
haiku = ChatBedrockConverse(
    model=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION, temperature=0
)

DEMO_QUESTIONS = [
    "How often should I brush my teeth?",
    "What dosage of amoxicillin should I take for a toothache?",
    "What is the capital of France?",
]


def build_qdrant_client() -> tuple[QdrantClient, str]:
    """Open the repo-local Qdrant store (path mode) — no Cloud, per scope."""
    store = VectorStore(
        collection_name=COLLECTION_NAME,
        qdrant_url="./data/qdrant_storage",
    )
    if not store.client.collection_exists(COLLECTION_NAME):
        raise SystemExit(
            "Collection 'occlusion' not found in ./data/qdrant_storage. "
            "Run `uv run python scripts/run_ingest.py` first."
        )
    return store.client, COLLECTION_NAME


def answer_questions(
    questions: list[str], client=None, collection_name: str = COLLECTION_NAME
) -> None:
    if client is None:
        client, collection_name = build_qdrant_client()
    retriever = make_retriever(client, collection_name, variant="hybrid")
    graph = build_graph(retriever=retriever, llm=haiku, confidence_threshold=0.7)

    for question in questions:
        print(f"\n=== Q: {question}")
        out = graph.invoke({"question": question})
        response = out["response"]
        print(
            json.dumps(
                response.model_dump(),
                indent=2,
                ensure_ascii=False,
            )
        )


def stream_one(graph, question: str) -> None:
    """Run one question via graph.stream (updates mode): each node prints
    live as it completes, then the final structured Answer/Refusal prints
    as JSON. Stream instead of invoke — you watch the pipeline work."""
    print(f"\n=== Q: {question}")
    response = None
    for update in graph.stream({"question": question}, stream_mode="updates"):
        for node, payload in update.items():
            if node == "guardrail":
                flag = "FLAGGED (out_of_scope)" if not payload["guardrail"].allowed else "allowed"
                print(f"  [guardrail] {flag}")
            elif node == "retrieve":
                print(f"  [retrieve] {len(payload['fused_chunks'])} chunks")
            elif node == "generate":
                print(f"  [generate] confidence={payload['candidate'].confidence:.2f}")
            elif node == "verify":
                check = payload["citation_check"]
                print(f"  [verify]   verified={check.verified} coverage={check.coverage:.0%}")
            elif node == "decide":
                response = payload["response"]
                verdict = "ACCEPTED" if response.kind == "answer" else "REFUSED"
                print(f"  [decide]   {verdict}")
    print(json.dumps(response.model_dump(), indent=2, ensure_ascii=False))


def chat_loop(graph) -> None:
    """Interactive REPL: one question per line, streamed node-by-node.
    Empty line, 'quit'/'exit'/'q', Ctrl-D or Ctrl-C exits."""
    print("Interactive mode — ask a dental question (or 'quit' to exit).")
    while True:
        try:
            question = input("\nYou > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            return
        if not question or question.lower() in {"q", "quit", "exit"}:
            print("Bye!")
            return
        stream_one(graph, question)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ask the dental RAG agent (fail-closed, cited answers)."
    )
    parser.add_argument(
        "question",
        nargs="*",
        help='Question(s) to ask. Omit to run the built-in demo questions.',
    )
    parser.add_argument(
        "--chat",
        action="store_true",
        help="Interactive loop: type questions, watch each node stream live.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    client, collection_name = build_qdrant_client()
    retriever = make_retriever(client, collection_name, variant="hybrid")
    graph = build_graph(retriever=retriever, llm=haiku, confidence_threshold=0.7)

    if args.chat:
        # Chat mode: hide INFO chatter so the streamed node lines and the
        # structured JSON are the show.
        logging.getLogger().setLevel(logging.WARNING)
        chat_loop(graph)
        return

    questions = [" ".join(args.question)] if args.question else DEMO_QUESTIONS
    answer_questions(questions, client, collection_name)


if __name__ == "__main__":
    main()
