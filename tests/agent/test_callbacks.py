"""SPEC_V2 §8 — callback capture tests (tmp files only, never real data)."""

import json
import logging

import pytest

from src.agent import callbacks


def test_append_writes_hash_not_raw_text(tmp_path):
    path = tmp_path / "callbacks.jsonl"
    rec = callbacks.append_callback(
        "Ana", "555-1234", "How do I treat my toothache?", "booking_failed", path=path
    )
    assert rec["question_hash"] != "How do I treat my toothache?"
    raw = path.read_text(encoding="utf-8")
    assert "How do I treat" not in raw
    assert "555-1234" in raw  # staff record keeps contact; logs must not
    assert callbacks.read_callbacks(path)[0]["name"] == "Ana"


def test_append_requires_name_and_phone(tmp_path):
    with pytest.raises(ValueError):
        callbacks.append_callback("", "555", "q", "r", path=tmp_path / "c.jsonl")
    with pytest.raises(ValueError):
        callbacks.append_callback("Ana", "  ", "q", "r", path=tmp_path / "c.jsonl")


def test_no_phi_in_logs(tmp_path, caplog):
    path = tmp_path / "callbacks.jsonl"
    with caplog.at_level(logging.INFO, logger="src.agent.callbacks"):
        callbacks.append_callback("Ana Secret", "555-9999", "q", "refusal", path=path)
    assert "Ana Secret" not in caplog.text
    assert "555-9999" not in caplog.text


def test_read_missing_file_returns_empty(tmp_path):
    assert callbacks.read_callbacks(tmp_path / "nope.jsonl") == []


def test_read_skips_bad_lines(tmp_path):
    path = tmp_path / "callbacks.jsonl"
    path.write_text('{"name": "A"}\nnot json\n', encoding="utf-8")
    assert callbacks.read_callbacks(path) == [{"name": "A"}]
