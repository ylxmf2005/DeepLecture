# Bold Proposal: AI-Powered Quiz Generation with Bloom-Calibrated Difficulty

## Innovation Summary

A three-stage LLM pipeline combining **knowledge extraction** (reusing cheatsheet patterns), **question generation with Bloom's taxonomy calibration**, and **distractor synthesis via misconception modeling** - leveraging the existing parallel execution infrastructure for efficient multi-question generation.

## Original User Request

> **Feature Request**: 在 DRY 前提下，利用现有 AI 功能，以优秀算法实现 Quiz 功能

This section preserves the user's exact requirements so that critique and reducer agents can verify alignment with the original intent.

## Research Findings

**Key insights from SOTA research:**

1. **Two-Stage Question Generation with Bloom's Taxonomy** ([arXiv:2408.04394](https://arxiv.org/abs/2408.04394)): The optimal prompting strategy is PS4 (Chain-of-Thought + skill definitions + example questions), achieving 81.37% high-quality questions with 72.77% Bloom skill-level alignment. Over-complex prompts (PS5) actually reduce quality.

2. **Student Choice Prediction for Distractor Generation** ([arXiv:2501.13125](https://arxiv.org/abs/2501.13125)): A two-stage approach using (1) a pairwise ranker that reasons about student misconceptions, then (2) Direct Preference Optimization (DPO) to generate distractors students are likely to select. This achieves "ranking accuracy comparable to human experts."

3. **TwinStar Dual-LLM Architecture** ([MDPI 2025](https://www.mdpi.com/2076-3417/15/6/3055)): Using separate Generator and Reviewer LLM roles improves question quality through automated critique and refinement.

4. **Spaced Repetition Integration** ([Brainscape, QuizCat](https://www.brainscape.com/academy/comparing-spaced-repetition-algorithms/)): SM-2 algorithm foundations with adaptive intervals based on difficulty rating (0-5 scale). A 2024 meta-analysis shows 12% exam score improvement for students using spaced repetition.

5. **In-Context Learning + RAG Hybrid** ([arXiv:2501.17397v1](https://arxiv.org/html/2501.17397v1)): ICL with few-shot examples combined with retrieval generates "more contextually accurate and relevant questions."

**Files checked for current implementation:**

- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/cheatsheet.py`: Verified two-stage LLM pipeline pattern (extraction -> rendering), context loading from subtitles
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/dto/cheatsheet.py`: Verified DTO patterns with dataclasses, `KnowledgeItem` structure
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/timeline.py`: Verified two-stage pattern with parallel execution (segmentation -> explanation in parallel)
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/note.py`: Verified outline-then-details pattern with `ParallelRunnerProtocol`
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/interfaces/parallel.py`: Verified `map_ordered()` signature with `ParallelGroup` literal type
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/prompts/registry.py`: Verified `BasePromptBuilder` pattern and registry factory
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/di/container.py`: Verified DI wiring patterns for use cases

## Proposed Solution

### Core Architecture: Three-Stage LLM Pipeline

Following the DRY principle, I propose extending the proven two-stage pattern to a three-stage pipeline optimized for quiz generation:

```
Stage 1: Knowledge Extraction (REUSE from Cheatsheet)
    └── KnowledgeItems with {category, content, criticality, tags}
         |
         v
Stage 2: Question Generation (NEW - Bloom-Calibrated)
    └── Multiple questions per KnowledgeItem, Bloom level targeting
         |
         v
Stage 3: Distractor Synthesis (NEW - Misconception Modeling)
    └── 3-4 distractors per MCQ via CoT misconception reasoning
```

### Key Components

#### 1. Domain Layer: Quiz Entities

**Files**:
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/dto/quiz.py`

**Responsibilities**:
- Define `QuizQuestion` dataclass (question_type, stem, options, correct_answer, bloom_level, difficulty_score, source_item_id)
- Define `QuizResult` dataclass with session tracking
- Define `DistractorSet` for MCQ options with plausibility scores
- Define `QuizSession` for tracking user progress and spaced repetition data

**LOC estimate**: ~120

```python
@dataclass
class QuizQuestion:
    """Single quiz question with metadata."""
    id: str
    question_type: Literal["mcq", "true_false", "fill_blank"]
    stem: str  # The question text
    options: list[str] | None  # For MCQ
    correct_answer: str | int  # Answer or index
    bloom_level: Literal["remember", "understand", "apply", "analyze", "evaluate", "create"]
    difficulty_score: float  # 0.0-1.0 computed from Bloom + content complexity
    source_knowledge_id: int  # Links back to KnowledgeItem
    explanation: str  # Why the answer is correct
    distractor_reasoning: list[str] | None  # Misconceptions each distractor targets
```

#### 2. Use Case: QuizUseCase

**Files**:
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/quiz.py`

**Responsibilities**:
- Orchestrate three-stage generation pipeline
- **Stage 1**: Reuse `CheatsheetUseCase._extract_knowledge_items()` logic (DRY)
- **Stage 2**: Generate questions via parallel LLM calls (reuse `ParallelRunnerProtocol`)
- **Stage 3**: Synthesize distractors with misconception reasoning
- Support adaptive quiz sessions with difficulty adjustment
- Integrate spaced repetition hooks for future learning analytics

**LOC estimate**: ~350

**Core Algorithm** (Bloom-calibrated generation):

```python
async def _generate_questions_for_item(
    self,
    item: KnowledgeItem,
    target_bloom_levels: list[str],
    questions_per_level: int,
) -> list[QuizQuestion]:
    """Generate questions targeting specific Bloom levels."""

    # PS4 strategy: CoT + Bloom definition + examples
    questions = []
    for bloom_level in target_bloom_levels:
        spec = self._prompt_registry.get("quiz_question_generation").build(
            knowledge_item=item,
            bloom_level=bloom_level,
            n_questions=questions_per_level,
            language=self._language,
        )
        raw = await self._llm.complete(spec.user_prompt, system_prompt=spec.system_prompt)
        questions.extend(self._parse_questions(raw, item.id, bloom_level))

    return questions

def _generate_parallel(self, items: list[KnowledgeItem], config: QuizConfig) -> list[QuizQuestion]:
    """Parallel question generation using existing infrastructure."""
    return self._parallel.map_ordered(
        items,
        lambda item: self._generate_questions_for_item(item, config.target_bloom_levels, config.questions_per_level),
        group="quiz_questions",  # New ParallelGroup
        on_error=lambda exc, item: [],
    )
```

#### 3. Prompts: Quiz Generation Prompts

**Files**:
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/prompts/quiz.py`

**Responsibilities**:
- `build_quiz_question_generation_prompt()`: Bloom-aware question generation with CoT
- `build_distractor_synthesis_prompt()`: Misconception-based distractor generation
- `build_quiz_review_prompt()`: Optional quality validation (TwinStar pattern)

**LOC estimate**: ~180

**Key Prompt Design** (based on PS4 research findings):

```python
def build_quiz_question_generation_prompt(
    knowledge_item: dict,
    bloom_level: str,
    n_questions: int,
    language: str,
) -> tuple[str, str]:
    """Build Bloom-calibrated question generation prompt.

    Uses PS4 strategy: CoT + skill definition + examples
    """

    bloom_definitions = {
        "remember": "Recall facts, terms, basic concepts. Verbs: define, list, name, recall.",
        "understand": "Explain ideas/concepts. Verbs: classify, describe, explain, summarize.",
        "apply": "Use information in new situations. Verbs: execute, implement, solve, use.",
        "analyze": "Draw connections among ideas. Verbs: differentiate, organize, compare.",
        "evaluate": "Justify decisions. Verbs: appraise, argue, defend, judge, critique.",
        "create": "Produce new work. Verbs: design, construct, develop, formulate.",
    }

    bloom_examples = {
        "remember": "Q: What is the formula for...? A: [exact formula]",
        "understand": "Q: Explain why X leads to Y. A: [conceptual explanation]",
        # ... examples for each level
    }

    system_prompt = f"""You are an expert educational assessment designer.
Your task is to create quiz questions at the {bloom_level.upper()} level of Bloom's Taxonomy.

BLOOM'S TAXONOMY LEVEL: {bloom_level.upper()}
Definition: {bloom_definitions[bloom_level]}

EXAMPLE QUESTION AT THIS LEVEL:
{bloom_examples[bloom_level]}

OUTPUT LANGUAGE: {language}

CHAIN OF THOUGHT PROCESS:
1. Identify the core concept in the knowledge item
2. Determine what cognitive skill the {bloom_level} level requires
3. Craft a question that specifically tests that skill
4. Ensure the question is unambiguous and has one clear correct answer

Output ONLY valid JSON array."""
```

#### 4. Storage: Quiz Storage Protocol

**Files**:
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/interfaces/quiz.py`
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/infrastructure/repositories/fs_quiz_storage.py`

**Responsibilities**:
- Store generated quiz banks per content_id
- Store user quiz sessions with responses
- Support spaced repetition metadata (next_review_at, ease_factor, interval)

**LOC estimate**: ~150

#### 5. API Routes: Quiz Endpoints

**Files**:
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/api/routes/quiz.py`

**Responsibilities**:
- `POST /quiz/generate`: Generate quiz bank (async task)
- `GET /quiz`: Get quiz bank for content
- `POST /quiz/session`: Start quiz session with difficulty settings
- `POST /quiz/submit`: Submit answer and get next question (adaptive)
- `GET /quiz/session/{session_id}`: Get session results

**LOC estimate**: ~180

#### 6. Prompt Registry Integration

**Files**:
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/prompts/registry.py` (modify)

**Responsibilities**:
- Register `QuizQuestionGenerationBuilder`
- Register `QuizDistractorSynthesisBuilder`
- Register `QuizReviewBuilder` (optional TwinStar validation)

**LOC estimate**: ~80 (additions to existing file)

### External Dependencies

**No new external dependencies required.** The solution reuses:
- Existing `LLMProviderProtocol` for LLM calls
- Existing `ParallelRunnerProtocol` for parallel execution
- Existing `SubtitleStorageProtocol` for context loading
- Existing filesystem storage patterns

## Benefits

1. **DRY Compliance**: Reuses ~70% of existing patterns (two-stage LLM, parallel execution, storage protocols, prompt registry). Stage 1 extraction can literally call existing cheatsheet extraction logic.

2. **Research-Backed Quality**: Implements PS4 prompting strategy (81.37% quality rate) and misconception-based distractor generation (expert-level ranking accuracy).

3. **Bloom's Taxonomy Calibration**: Questions are explicitly targeted at cognitive levels, enabling:
   - Difficulty progression in adaptive sessions
   - Learning analytics on student cognitive skill gaps
   - Curriculum alignment reporting

4. **Scalable Architecture**: Parallel question generation scales linearly with content size using existing `ThreadPoolParallelRunner`.

5. **Spaced Repetition Ready**: Storage schema includes fields for SM-2-style scheduling, enabling future integration with flashcard/review systems.

6. **Multi-Question Type Support**: Architecture supports MCQ, True/False, and Fill-in-blank, extensible to short-answer with rubric generation.

## Trade-offs

1. **Complexity**: Three-stage pipeline vs. simpler single-stage approach
   - Mitigation: Each stage is isolated and testable; Stage 1 is fully reused from cheatsheet

2. **Learning curve**: Bloom's taxonomy concepts for prompt engineering
   - Mitigation: Bloom definitions are embedded in prompts; developers only configure target levels

3. **Failure modes**:
   - LLM may generate invalid JSON: Handled by existing `parse_llm_json()` utility
   - Questions may not align with intended Bloom level: TwinStar review stage can validate
   - Distractors may be too easy/obvious: Misconception reasoning in prompt addresses this
   - Rate limits on parallel calls: Existing `RateLimiter` handles this

4. **Cost**: Three LLM calls per knowledge item (question + distractor + optional review)
   - Mitigation: Review stage is optional; distractor synthesis can batch multiple questions

## Implementation Estimate

**Total LOC**: ~1060 (Medium-Large feature)

**Breakdown**:
| Component | LOC |
|-----------|-----|
| DTOs (`quiz.py`) | ~120 |
| Use Case (`quiz.py`) | ~350 |
| Prompts (`prompts/quiz.py`) | ~180 |
| Storage Interface + Implementation | ~150 |
| API Routes | ~180 |
| Prompt Registry Additions | ~80 |

**Documentation**: ~100 LOC (API docs, prompt design docs)
**Tests**: ~250 LOC (unit tests for DTOs, prompts; integration tests for use case)

**Grand Total**: ~1410 LOC

**Recommended approach**: Use milestone commits for incremental progress:
- Milestone 1: DTOs + Storage (foundational)
- Milestone 2: Prompts + Registry integration
- Milestone 3: Use Case with Stage 1-2
- Milestone 4: Stage 3 (distractors) + API routes
- Milestone 5: Tests + Documentation

---

## Sources

- [Automatic Question Generation Survey (Springer)](https://link.springer.com/article/10.1186/s41039-021-00151-1)
- [AQG Methodologies Review (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9886210/)
- [Automated Educational Question Generation at Different Bloom's Skill Levels (arXiv:2408.04394)](https://arxiv.org/abs/2408.04394)
- [Generating Plausible Distractors via Student Choice Prediction (arXiv:2501.13125)](https://arxiv.org/abs/2501.13125)
- [TwinStar: Dual-LLM Question Generation (MDPI 2025)](https://www.mdpi.com/2076-3417/15/6/3055)
- [How Teachers Can Use LLMs and Bloom's Taxonomy (arXiv:2401.05914)](https://arxiv.org/html/2401.05914v1)
- [Comparing Spaced Repetition Algorithms (Brainscape)](https://www.brainscape.com/academy/comparing-spaced-repetition-algorithms/)
- [In-Context Learning and RAG for Question Generation (arXiv:2501.17397)](https://arxiv.org/html/2501.17397v1)
