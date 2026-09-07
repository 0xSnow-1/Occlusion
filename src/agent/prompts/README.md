# Prompts Directory

This directory contains prompt templates used by the agent graph, organized for easy prompt engineering experimentation and versioning.

## Purpose
Prompt templates are used in the `generate_node` of the agent graph to construct messages sent to the LLM. Each prompt should:
1. Include the user's question
2. Include retrieved chunks with `[SRC:doc_id]` anchor tokens preceding each chunk
3. Instruct the LLM to answer based only on the provided context
4. Instruct the LLM to cite sources inline using `[SRC:doc_id]` format
5. Instruct the LLM to refuse with "I don't have enough information" if uncertain

## Prompt Template Structure

Each prompt template is a Markdown file (`.md`) that can contain:
- Template variables: `{question}` and `{context}` that get replaced at runtime
- Instructions for the LLM
- Examples or few-shot demonstrations (if desired)
- Version tracking and metadata
- Chain-of-thought reasoning structures
- Role definitions and behavioral guidelines

## Available Prompt Templates

Use `get_available_prompts()` to see all available templates, or list the `.md` files in this directory.

### Current Templates:
- `dental_qa_base.md` - Standard dental QA prompt with clear instructions
- `dental_qa_cot.md` - Chain-of-thought version for complex reasoning
- `dental_qa_simple.md` - Minimal template for testing

## Usage Examples

### Basic Usage in Code:
```python
from src.agent.prompts import format_dental_qa_prompt

prompt = format_dental_qa_prompt(
    question=state["question"],
    chunks=state["fused_chunks"],
    template_name="dental_qa_base"  # Change to experiment with different prompts
)
```

### Advanced Prompt Engineering Workflow:
1. **Create a new template**: Copy an existing one or create new
   ```bash
   cp src/agent/prompts/dental_qa_base.md src/agent/prompts/dental_qa_v2_experiment.md
   ```

2. **Edit the template**: Modify instructions, add few-shot examples, change structure
3. **Test the prompt**: Change the template_name in your code to compare results
4. **Track versions**: Use date/version metadata in your templates
5. **A/B testing**: Create multiple versions and compare performance metrics

## Template Variables Available

When creating or editing templates, you have access to:
- `{question}`: The user's original question
- `{context}`: Formatted chunks with `[SRC:doc_id]` annotations

Example context format:
```
[SRC:nhs-gum-disease-001] Brush twice a day with fluoride toothpaste to prevent gum disease...
[SRC:ada-caries-prevention-002] Fluoride helps remineralize early enamel lesions...
```

## Best Practices for Prompt Engineering

1. **Be Specific**: Clear instructions yield more consistent results
2. **Emphasize Grounding**: Remind the LLM to use only provided context
3. **Citation Format**: Always reinforce the `[SRC:doc_id]` format requirement
4. **Refusal Guidance**: Provide clear fallback when information is insufficient
5. **Role Definition**: Define the assistant's persona and expertise level
6. **Length Control**: Consider implicit or explicit length constraints
7. **Safety First**: Especially important in health domains - emphasize when to seek professional help

## Versioning and Experimentation

To support your prompt engineering workflow:
- Create versioned templates: `dental_qa_v1.md`, `dental_qa_v2.md`, etc.
- Use date stamps: `dental_qa_2026-09-06.md`
- Create experiment branches: `dental_qa_cot_experiment.md`
- Document changes in the template header or comments

The graph is designed to work with any prompt template that follows the basic structure, making it easy to:
- A/B test different prompting strategies
- Experiment with chain-of-thought vs direct approaches
- Test few-shot learning examples
- Optimize for specific dental subdomains (orthodontics, periodontics, etc.)