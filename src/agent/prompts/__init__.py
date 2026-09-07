"""Prompt loading utilities for the dental RAG agent."""

from __future__ import annotations

from pathlib import Path

from src.agent.schemas import RetrievedChunk


def load_prompt_template(prompt_name: str) -> str:
    """Load a prompt template from the prompts directory.
    
    Args:
        prompt_name: Name of the prompt file (without .md extension)
        
    Returns:
        The prompt template as a string
        
    Raises:
        FileNotFoundError: If the prompt file doesn't exist
    """
    prompts_dir = Path(__file__).parent
    prompt_path = prompts_dir / f"{prompt_name}.md"
    
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
    
    return prompt_path.read_text(encoding="utf-8")


def format_dental_qa_prompt(
    question: str, 
    chunks: list[RetrievedChunk],
    template_name: str = "dental_qa_base"
) -> str:
    """Format a dental QA prompt with retrieved chunks.
    
    Args:
        question: The user's question
        chunks: List of retrieved chunks with [SRC:doc_id] annotations
        template_name: Name of the prompt template to use
        
    Returns:
        Formatted prompt ready for LLM consumption
    """
    # Load the template
    template = load_prompt_template(template_name)
    
    # Format chunks with [SRC:doc_id] annotations
    context_parts = []
    for chunk in chunks:
        context_parts.append(f"[SRC:{chunk.doc_id}] {chunk.text}")
    
    context = "\n\n".join(context_parts)
    
    # Simple template formatting - can be extended for more complex templating
    formatted_prompt = template.replace("{question}", question)
    formatted_prompt = formatted_prompt.replace("{context}", context)
    
    return formatted_prompt


def get_available_prompts() -> list[str]:
    """Get list of available prompt templates.
    
    Returns:
        List of prompt names (without .md extension)
    """
    prompts_dir = Path(__file__).parent
    return [f.stem for f in prompts_dir.glob("*.md") if f.name != "README.md"]


__all__ = [
    "load_prompt_template",
    "format_dental_qa_prompt", 
    "get_available_prompts",
]