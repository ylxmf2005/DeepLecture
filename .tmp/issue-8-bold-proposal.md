# Bold Proposal: Optimized Video-to-Notes Generation

## Innovation Summary

Replace the current "N parts x full context" parallel expansion with a three-stage **Extract-Assign-Render** pipeline: (1) extract a deduplicated concept graph from the transcript, (2) assign concepts to outline parts during outline generation, then (3) expand each part using only its assigned context segments -- eliminating repetition at the architectural level and cutting token usage by 60-80%.

## Research Findings

1. **Map-Reduce with Concept Reduction** (Google Cloud Blog): The "reduce" step should merge/deduplicate, not just concatenate.
2. **Hierarchical Summarization with CoT** (CoTHSSum, Springer 2025): Structured intermediate representations outperform direct summarization.
3. **One-Shot vs. Chunked Tradeoffs** (Snowflake RAG study): For detailed notes, retrieval/chunking still outperforms stuffing. Key is concept-aligned chunks.
4. **G2: Guided Generation for Diversity** (arXiv 2025): Making later steps aware of earlier output prevents repetition.
5. **Cheatsheet Pattern (Internal)**: Two-stage extract-render naturally prevents repetition.

## Strategy A: Outline with Concept Assignment + Targeted Context (Recommended)

Three-stage pipeline: Outline+Assignment → Parallel Part Expansion with targeted context → Join
- Solves repetition: concepts assigned to exactly one part
- Solves token waste: 60-80% reduction (only relevant segments per part)
- Preserves parallelism
- ~350 LOC

## Strategy B: Knowledge Extraction + Rendering (Cheatsheet Pattern)

Two-stage: Extract KnowledgeItems → Render full note in one call
- Maximum token efficiency (2 LLM calls total)
- Zero repetition
- Risk: output length limits for long notes
- ~400 LOC

## Strategy C: Sequential Generation with "Previously Covered" Tracking

Sequential pipeline with accumulating concept list
- Simplest change (~150 LOC)
- Does NOT solve token waste
- Loses parallelism
- Repetition reduced but not eliminated

## Comparative Analysis

| Criterion | A (Concept Assignment) | B (Extract-Render) | C (Sequential) |
|---|---|---|---|
| Repetition | Structural | Structural | Soft |
| Token reduction | 60-80% | 80-90% | 0% |
| Parallelism | Yes | N/A | No |
| Quality risk | Low | Medium (length limits) | Low |
| LOC | ~350 | ~400 | ~150 |

**Recommendation: Strategy A** — best quality-to-complexity ratio.
