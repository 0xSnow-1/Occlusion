"""Blocker 7 (B3): exact OGL sentence in UI disclaimer and answer footer."""

from __future__ import annotations

from src.agent.schemas import RetrievedChunk
from src.ui.app import (
    DISCLAIMER,
    OGL_ATTRIBUTION,
    citation_link,
)

EXACT = (
    "Contains public sector information licensed "
    "under the Open Government Licence v3.0."
)


def _chunk(doc_id="dental-abscess", url="https://www.nhs.uk/conditions/dental-abscess/"):
    return RetrievedChunk(doc_id=doc_id, text="NHS abscess guidance.", source_url=url)


class TestOglDisclaimer:
    def test_constant_is_exact_sentence(self):
        assert OGL_ATTRIBUTION == EXACT

    def test_disclaimer_contains_exact_sentence(self):
        assert EXACT in DISCLAIMER


class TestCitationLink:
    def test_link_when_url_known(self):
        assert citation_link("dental-abscess", "https://www.nhs.uk/conditions/dental-abscess/") == (
            "[dental-abscess](https://www.nhs.uk/conditions/dental-abscess/)"
        )

    def test_chip_fallback_for_legacy_chunks(self):
        assert citation_link("dental-abscess", None) == "`dental-abscess`"
