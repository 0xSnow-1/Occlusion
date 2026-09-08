#!/bin/bash
# Reference path: the honest completion — run the live batch runner once per
# question through the real graph (frozen :memory: retriever + live Bedrock
# Haiku) and record its exact outputs. Proves the intended result is
# reachable; does not hard-code answers.
set -euo pipefail
mkdir -p /logs
python3 /app/run_live.py --questions /app/questions.jsonl --out /logs/responses.jsonl --calls /logs/calls.jsonl --meta /logs/meta.json
