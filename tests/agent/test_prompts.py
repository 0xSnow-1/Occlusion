"""Behavioral tests for prompt loading and the v2.3 template contract.

Executes the public prompt interface (load/format) and asserts on the
rendered output — not on source text.
"""

import pytest

from src.agent.prompts import (
    format_dental_qa_prompt,
    get_available_prompts,
    load_prompt_template,
)
from src.agent.schemas import RetrievedChunk


def _chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(doc_id="gum-disease", text="Gums bleed when plaque builds up."),
        RetrievedChunk(doc_id="flossing-brushing", text="Brush twice daily with fluoride toothpaste."),
    ]


class TestLoadPromptTemplate:
    def test_missing_template_raises(self):
        with pytest.raises(FileNotFoundError):
            load_prompt_template("no-such-template")

    def test_v23_available(self):
        assert "dental_qa_v2.3" in get_available_prompts()


class TestFormatV23:
    def test_embeds_question_and_src_anchored_context(self):
        rendered = format_dental_qa_prompt(
            "Why do my gums bleed?", _chunks(), template_name="dental_qa_v2.3"
        )
        assert "Why do my gums bleed?" in rendered
        assert "[SRC:gum-disease] Gums bleed when plaque builds up." in rendered
        assert "[SRC:flossing-brushing] Brush twice daily with fluoride toothpaste." in rendered

    def test_no_unfilled_placeholders(self):
        rendered = format_dental_qa_prompt("Q?", _chunks(), template_name="dental_qa_v2.3")
        assert "{question}" not in rendered
        assert "{context}" not in rendered

    def test_xml_sections_and_self_check_contract(self):
        rendered = format_dental_qa_prompt("Q?", _chunks(), template_name="dental_qa_v2.3")
        for section in ("<role>", "<context>", "<question>", "<instructions>", "<examples>"):
            assert section in rendered
        # Self-check line: every sentence must carry a valid citation token.
        assert "Before you finish, check that every sentence" in rendered
        # Bare-ID citation contract (no SRC: prefix in the citations list).
        assert "bare doc_ids" in rendered

    def test_boundary_few_shot_present(self):
        rendered = format_dental_qa_prompt("Q?", _chunks(), template_name="dental_qa_v2.3")
        assert "boundary question" in rendered
