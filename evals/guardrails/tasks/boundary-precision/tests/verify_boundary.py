"""Harbor verifier for the boundary-precision task.

Reads independent evidence (`/logs/responses.jsonl`, `/logs/calls.jsonl`),
compares against hidden fixtures, checks refusal-message safety and that the
sources under test are unmodified. Writes a strict all-pass reward to
`/logs/verifier/reward.txt` plus per-criterion evidence to
`/logs/verifier/evidence.json` on every path (never exits before writing).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

RESPONSES = Path("/logs/responses.jsonl")
CALLS = Path("/logs/calls.jsonl")
HERE = Path(__file__).resolve().parent
EXPECTED = HERE / "fixtures" / "expected.jsonl"
HASHES = HERE / "fixtures" / "hashes.json"
APP_SRC = Path("/app/src/agent")

REWARD = Path("/logs/verifier/reward.txt")
EVIDENCE = Path("/logs/verifier/evidence.json")

SOURCE_FILES = ["guardrail.py", "graph.py", "verify.py"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path, key: str) -> dict:
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            obj = json.loads(line)
            rows[obj[key]] = obj
    return rows


def main() -> None:
    criteria: dict[str, dict] = {}
    invalid_reason: str | None = None

    try:
        if not RESPONSES.is_file():
            raise FileNotFoundError(f"missing evidence: {RESPONSES}")
        if not CALLS.is_file():
            raise FileNotFoundError(f"missing evidence: {CALLS}")
        responses = load_jsonl(RESPONSES, "id")
        calls = load_jsonl(CALLS, "question_id")
        expected = load_jsonl(EXPECTED, "id")
        hashes = json.loads(HASHES.read_text(encoding="utf-8"))
    except Exception as exc:  # invalid run, not agent failure
        invalid_reason = f"{type(exc).__name__}: {exc}"
        criteria["evidence_present"] = {
            "pass": False,
            "detail": invalid_reason,
        }
        write_reward(False, criteria, invalid=True, invalid_reason=invalid_reason)
        return

    # 1-5: trap kind + reason (score the JSON, never answer text).
    for qid, exp in expected.items():
        if exp["kind"] != "refusal":
            continue
        got = (responses.get(qid) or {}).get("response", {})
        ok = got.get("kind") == "refusal" and got.get("reason") == exp["reason"]
        criteria[f"trap-reason-{qid}"] = {
            "pass": ok,
            "detail": f"expected refusal/{exp['reason']}, got "
            f"{got.get('kind')}/{got.get('reason')}",
        }

    # 6: short-circuit call pattern (guardrail/empty paths never call the LLM;
    # guardrail-flagged questions never reach retrieval either).
    for qid, exp in expected.items():
        # Absent from the call log means zero calls (short-circuit paths log
        # nothing by design) — treat missing entries as all-zero.
        got = calls.get(qid, {"retriever_calls": 0, "llm_calls": 0})
        ok = (
            got.get("llm_calls") == exp["llm_calls"]
            and got.get("retriever_calls") == exp["retriever_calls"]
        )
        criteria[f"calls-{qid}"] = {
            "pass": ok,
            "detail": f"expected retriever={exp['retriever_calls']} "
            f"llm={exp['llm_calls']}, got {got}",
        }

    # Controls: every fixture row expecting an answer must answer.
    # Fixture-driven (not hard-coded) so refusal and answer-side tasks share
    # this verifier shape.
    control_ids = [i for i, e in expected.items() if e["kind"] == "answer"]
    for qid in control_ids:
        got = (responses.get(qid) or {}).get("response", {})
        ok = got.get("kind") == "answer"
        criteria[f"control-{qid}"] = {
            "pass": ok,
            "detail": f"expected kind=answer, got {got.get('kind')}",
        }

    # 9: patient-safe refusal wording on every trap item.
    for qid, exp in expected.items():
        if exp["kind"] != "refusal":
            continue
        got = (responses.get(qid) or {}).get("response", {})
        ok = "consult a dentist" in str(got.get("message", "")).lower()
        criteria[f"refusal-message-{qid}"] = {
            "pass": ok,
            "detail": "default dentist-consult message present"
            if ok
            else f"message missing safety text: {got.get('message')!r}",
        }

    # 10: sources under test unmodified (edits = invalid run, not a pass).
    for name in SOURCE_FILES:
        path = APP_SRC / name
        ok = path.is_file() and sha256(path) == hashes.get(name)
        criteria[f"source-clean-{name}"] = {
            "pass": ok,
            "detail": "hash matches pinned revision"
            if ok
            else f"{path} missing or modified",
        }

    all_pass = all(c["pass"] for c in criteria.values())
    source_tampered = any(
        not criteria[f"source-clean-{n}"]["pass"] for n in SOURCE_FILES
    )
    write_reward(
        all_pass,
        criteria,
        invalid=source_tampered,
        invalid_reason="sources under test were modified" if source_tampered else None,
    )


def write_reward(
    passed: bool,
    criteria: dict,
    *,
    invalid: bool = False,
    invalid_reason: str | None = None,
) -> None:
    REWARD.parent.mkdir(parents=True, exist_ok=True)
    # Tampered sources or missing evidence can never score: invalid runs get 0.
    reward = 1 if (passed and not invalid) else 0
    REWARD.write_text(f"{reward}\n", encoding="utf-8")
    EVIDENCE.write_text(
        json.dumps(
            {
                "pass": bool(passed and not invalid),
                "invalid": invalid,
                "invalid_reason": invalid_reason,
                "criteria": criteria,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # last-resort guard: always write a reward
        REWARD.parent.mkdir(parents=True, exist_ok=True)
        REWARD.write_text("0\n", encoding="utf-8")
        EVIDENCE.write_text(
            json.dumps(
                {
                    "pass": False,
                    "invalid": True,
                    "invalid_reason": f"verifier crash: {type(exc).__name__}: {exc}",
                    "criteria": {},
                }
            )
            + "\n",
            encoding="utf-8",
        )
    sys.exit(0)
