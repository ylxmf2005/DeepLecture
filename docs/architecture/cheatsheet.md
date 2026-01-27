# Cheatsheet Architecture

## Overview

The Cheatsheet feature generates high-density, scannable reference sheets from video content (subtitles/slides) optimized for open-book exam lookup and quick review.

## Design Goals

- **High Information Density**: Compress key knowledge points, not simple summaries
- **Reduced Memory Burden**: Assume user understanding, focus on hard-to-remember facts
- **Smart Filtering**: Remove easily derivable/redundant information
- **Scannable Format**: Optimize for tables, formulas, hierarchical lists

## Data Flow

```
Subtitles/Slides → Extraction → Filtering → Rendering → Storage
                   (Stage 1)    (inline)    (Stage 2)
```

### Two-Stage LLM Pipeline

**Stage 1: Knowledge Extraction**
- Input: Subtitle segments, slide text
- Process: Extract `KnowledgeItem` list with criticality scores
- Output: JSON array of structured knowledge items

**Stage 2: Dense Rendering**
- Input: Filtered knowledge items (criticality >= threshold)
- Process: Render to scannable Markdown format
- Output: High-density cheatsheet content

### Fallback Strategy

If JSON parsing fails in Stage 1, fall back to single-stage direct Markdown generation.

## Key Data Structures

### KnowledgeItem

```python
@dataclass
class KnowledgeItem:
    category: str      # formula | definition | condition | algorithm | constant | example
    content: str       # The actual content
    criticality: str   # high | medium | low
    tags: list[str]    # Topic tags for grouping
```

### Criticality Levels

| Level | Description | Keep? |
|-------|-------------|-------|
| high | Formulas, constants, key definitions | Always |
| medium | Important concepts, conditions | By default |
| low | Derivable facts, context | Only if min_criticality=low |

## Storage

- Path: `content/{content_id}/cheatsheet/cheatsheet.md`
- Format: Markdown with LaTeX math support
- Atomic writes via tempfile + os.replace

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/cheatsheet` | Retrieve existing cheatsheet |
| POST | `/api/cheatsheet` | Save cheatsheet content |
| POST | `/api/cheatsheet/generate` | Generate new cheatsheet (async) |

## Constraints

- Two-stage LLM pipeline (not three) to control costs
- No `derivable_from` dependency graph (simplicity)
- No DB schema changes (cheatsheet status not persisted to metadata)
