# Context Summary: Note Generation Optimization (Token Reduction & Deduplication)

## Feature Understanding
**Intent**: Research industry-standard video-to-notes generation methods (including one-shot approaches) and propose 1-3 optimal improvement strategies to address current system issues: content redundancy across parts and excessive token costs.

## Relevant Files

### Source Files
- `src/deeplecture/use_cases/note.py` — Main note generation orchestration. Two-stage pipeline: (1) build outline via `_build_outline()`, (2) parallel part generation via `_generate_parts_parallel()`. Each part receives full `context_block`.
- `src/deeplecture/use_cases/prompts/note.py` — Prompt construction for outline and part generation.
- `src/deeplecture/infrastructure/parallel_runner.py` — ThreadPoolExecutor-based parallel execution.
- `src/deeplecture/use_cases/cheatsheet.py` — Successful two-stage pipeline: knowledge extraction → rendering. Uses structured `KnowledgeItem` objects.
- `src/deeplecture/use_cases/quiz.py` — Another two-stage example reusing cheatsheet's extraction stage.

### Constraints
- Clean Architecture: use_cases → interfaces dependency direction
- `ParallelRunnerProtocol.map_ordered()` has no inter-task shared state
- API endpoint expects `GeneratedNoteResult` with `outline` and `content`
- `LLMConfig.max_rpm = 600`
- No partial result storage currently

### Key Pattern: Cheatsheet Knowledge Extraction
Cheatsheet uses structured intermediate representation (KnowledgeItem) that enables filtering, deduplication, and reuse. Note generation lacks this.

## Current Problems
1. Each Part receives full context_block (N parts × full transcript = massive token waste)
2. Parts generated in parallel have zero awareness of each other → content repetition
3. Kerckhoffs principle, CIA triad etc repeated in 3-4 Parts

## Complexity: Full path (SOTA research needed, 5-8 files, 280-500 LOC)
