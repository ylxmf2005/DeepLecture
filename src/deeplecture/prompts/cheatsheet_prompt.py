"""
Prompt builders for AI-generated cheatsheets (open-book exam review).

Two-stage pipeline:
1. Extraction: Extract KnowledgeItems from content with criticality scoring
2. Rendering: Render items into scannable Markdown format
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deeplecture.use_cases.dto.cheatsheet import KnowledgeItem


def build_cheatsheet_extraction_prompts(
    *,
    language: str,
    context_block: str,
    user_instruction: str,
    min_criticality: str,
    subject_type: str,
) -> tuple[str, str]:
    """
    Build prompts for knowledge extraction stage.

    Args:
        language: Output language.
        context_block: Lecture content (subtitle and/or slides).
        user_instruction: User-provided instruction.
        min_criticality: Minimum criticality to include (high/medium/low).
        subject_type: Subject type for extraction heuristics (stem/humanities/auto).

    Returns:
        Tuple of (system_prompt, user_prompt).
    """
    # Subject-specific guidance
    subject_guidance = ""
    if subject_type == "stem":
        subject_guidance = (
            "This is STEM content. Prioritize:\n"
            "- Formulas and equations (especially with multiple variables)\n"
            "- Algorithm steps and complexity analysis\n"
            "- Physical/chemical constants and units\n"
            "- Boundary conditions and constraints\n"
            "- Derivation steps that are hard to reproduce\n"
        )
    elif subject_type == "humanities":
        subject_guidance = (
            "This is humanities content. Prioritize:\n"
            "- Key dates, names, and events\n"
            "- Definitions of specialized terms\n"
            "- Classification systems and taxonomies\n"
            "- Theoretical frameworks and their components\n"
            "- Primary source references\n"
        )
    else:  # auto
        subject_guidance = (
            "Analyze the content and identify what is hard to derive or memorize:\n"
            "- Formulas, equations, algorithms\n"
            "- Definitions and specialized terminology\n"
            "- Numerical values, constants, thresholds\n"
            "- Conditions, constraints, edge cases\n"
            "- Examples that illustrate key concepts\n"
        )

    # Criticality guidance
    criticality_desc = {
        "high": "only HIGH criticality items (essential, exam-critical)",
        "medium": "MEDIUM and HIGH criticality items (important concepts)",
        "low": "all items including LOW criticality (comprehensive coverage)",
    }
    crit_filter = criticality_desc.get(min_criticality, criticality_desc["medium"])

    system_prompt = f"""\
You are an expert knowledge extractor for open-book exam preparation.
Your task is to extract discrete, self-contained knowledge items from lecture content.

EXTRACTION PRINCIPLES:
1. HIGH DENSITY: Each item should be information-dense but scannable
2. SELF-CONTAINED: Each item should make sense without surrounding context
3. DERIVABILITY TEST: Prioritize items that are hard to derive or recall
   - Include: formulas, constants, exact definitions, conditions
   - Exclude: obvious facts, easily derived conclusions, general principles

CRITICALITY SCORING:
- HIGH: Essential for the exam, hard to derive, easy to forget
- MEDIUM: Important but somewhat derivable or memorable
- LOW: Nice to know, easily derivable or common knowledge

CATEGORY TYPES:
- formula: Mathematical equations, formulas, identities
- definition: Technical terms, precise definitions
- condition: Prerequisites, constraints, boundary conditions
- algorithm: Step-by-step procedures, pseudo-code
- constant: Numerical values, physical constants, thresholds
- example: Worked examples, canonical cases

{subject_guidance}

OUTPUT FORMAT:
Return a JSON object with a "items" array.
Each item has: category, content, criticality, tags.

Filter to include: {crit_filter}.
Output language: {language}.
Do NOT wrap JSON in markdown fences."""

    user_lines = [
        "Extract knowledge items from this lecture content.",
        "Focus on information that is:",
        "- Hard to derive from first principles",
        "- Easy to forget or confuse",
        "- Frequently tested in exams",
    ]

    if user_instruction:
        user_lines.append(f"\nUser instruction: {user_instruction}")

    user_lines.append(f"\nLecture content:\n{context_block}")

    user_lines.append("""
Return JSON in this format:
{
  "items": [
    {
      "category": "formula",
      "content": "E = mc²",
      "criticality": "high",
      "tags": ["physics", "relativity"]
    },
    {
      "category": "definition",
      "content": "Entropy: measure of disorder in a system, S = k_B ln(W)",
      "criticality": "high",
      "tags": ["thermodynamics"]
    }
  ]
}""")

    user_prompt = "\n\n".join(user_lines)
    return system_prompt, user_prompt


def build_cheatsheet_rendering_prompts(
    *,
    language: str,
    items: list[KnowledgeItem],
    target_pages: int,
    user_instruction: str,
) -> tuple[str, str]:
    """
    Build prompts for rendering stage.

    Args:
        language: Output language.
        items: Extracted KnowledgeItems.
        target_pages: Approximate target length in pages.
        user_instruction: User-provided instruction.

    Returns:
        Tuple of (system_prompt, user_prompt).
    """
    system_prompt = f"""\
You are a cheatsheet designer for open-book exams.
Your task is to arrange knowledge items into a scannable, high-density Markdown document.

DESIGN PRINCIPLES:
1. SCANNABILITY: Use visual hierarchy for quick lookup during exams
2. GROUPING: Cluster related items together by topic/category
3. BREVITY: Compress text while preserving precision
4. VISUAL AIDS: Use tables, bullet lists, and formatting strategically

FORMATTING GUIDELINES:
- Use level-2 headings (##) for major sections
- Use tables for comparing related concepts
- Use code blocks for algorithms and formulas
- Use bold for key terms, italics for definitions
- Use horizontal rules to separate major sections

Target length: approximately {target_pages} pages when printed.
Output language: {language}.
Output Markdown directly, no explanations or commentary."""

    # Convert items to JSON-like format for the prompt
    items_json = []
    for item in items:
        items_json.append(
            f"  - [{item.category.upper()}] ({item.criticality}) {item.content}"
        )
    items_text = "\n".join(items_json)

    user_lines = [
        "Arrange these extracted knowledge items into a well-organized cheatsheet.",
        "",
        "Knowledge items to include:",
        items_text,
    ]

    if user_instruction:
        user_lines.append(f"\nUser instruction: {user_instruction}")

    user_lines.append("""
Output a complete Markdown cheatsheet with:
- Clear section organization by topic
- Tables where comparison is useful
- Proper formatting for formulas (LaTeX math)
- No redundant information""")

    user_prompt = "\n\n".join(user_lines)
    return system_prompt, user_prompt
