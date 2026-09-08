"""Citation verification for the agent graph (TODO Phase 5.4)."""

from __future__ import annotations

import logging
import re
from typing import List

from src.agent.schemas import Answer, CitationCheck, RetrievedChunk

logger = logging.getLogger(__name__)


def extract_citations(text: str) -> List[str]:
    """Extract all [SRC:doc_id] tokens from text.
    
    Args:
        text: Input text potentially containing citation tokens
        
    Returns:
        List of doc_ids found in citation tokens, in order of appearance
    """
    pattern = r'\[SRC:([^\]]+)\]'
    return re.findall(pattern, text)


def verify_citations(answer: Answer, retrieved_chunks: List[RetrievedChunk]) -> CitationCheck:
    """Verify that all cited doc_ids in answer exist in retrieved chunks.
    
    Implements fail-closed verification: zero citations or any fabricated ID 
    results in verified=False.
    
    Args:
        answer: The LLM's structured output answer
        retrieved_chunks: Chunks retrieved for this query
        
    Returns:
        CitationCheck with verification results
    """
    # Extract cited IDs from answer
    cited_ids = extract_citations(answer.answer)
    
    # Get set of retrieved doc_ids for fast lookup
    retrieved_ids = {chunk.doc_id for chunk in retrieved_chunks}
    
    # Track verification metrics
    fabricated_ids = []
    matches = 0
    
    for doc_id in cited_ids:
        if doc_id in retrieved_ids:
            matches += 1
        else:
            fabricated_ids.append(doc_id)
    
    total = len(cited_ids)
    
    # Fail-closed: verified only if we have citations AND none are fabricated
    verified = (total > 0) and (len(fabricated_ids) == 0)
    
    # Coverage: proportion of citations that are valid (0 if no citations)
    coverage = matches / total if total > 0 else 0.0
    
    return CitationCheck(
        verified=verified,
        cited_ids=cited_ids,
        retrieved_ids=list(retrieved_ids),
        fabricated_ids=fabricated_ids,
        matches=matches,
        total=total,
        coverage=coverage,
    )


def strip_fabricated_tokens(text: str, fabricated_ids: List[str]) -> str:
    """Remove [SRC:fabricated_id] tokens from text.
    
    Args:
        text: Input text potentially containing citation tokens
        fabricated_ids: List of doc_ids to strip from text
        
    Returns:
        Text with fabricated citation tokens removed (leaves legitimate ones)
    """
    if not fabricated_ids:
        return text
        
    # Build regex pattern to match any of the fabricated IDs
    escaped_ids = [re.escape(fid) for fid in fabricated_ids]
    pattern = r'\[SRC:(%s)\]' % '|'.join(escaped_ids)
    
    # Replace fabricated tokens with empty string
    return re.sub(pattern, '', text)


__all__ = [
    "extract_citations",
    "verify_citations", 
    "strip_fabricated_tokens",
]