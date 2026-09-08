#!/bin/bash
# Reference path: the honest completion — run the batch runner once per
# question through the real graph and record its exact outputs.
# Proves the intended result is reachable; does not hard-code answers.
set -euo pipefail
mkdir -p /logs
python3 /app/run_batch.py --questions /app/questions.jsonl --out /logs/responses.jsonl --calls /logs/calls.jsonl
