#!/bin/bash
# Harbor verifier entry point: runs after agent work ends.
# Reads independent evidence, writes reward + criterion evidence.
# Always exits 0 after writing the reward (infrastructure failure is
# reported via invalid flags in evidence.json, never as a bare nonzero exit).
set -u
mkdir -p /logs/verifier
python3 /tests/verify_boundary.py
[ -f /logs/verifier/reward.txt ] || echo 0 > /logs/verifier/reward.txt
exit 0
