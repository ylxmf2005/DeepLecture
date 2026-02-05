# External Consensus Review Task

You are an expert software architect tasked with synthesizing a consensus implementation plan from three different perspectives on the same feature.

## Context

Three specialized agents have analyzed the following requirement:

**Feature Request**: Unknown Feature

Each agent provided a different perspective:
1. **Bold Proposer**: Innovative, SOTA-driven approach, which searched from internet for cutting-edge techniques.
   - The bold proposal includes the "Original User Request" section with the verbatim feature description.
2. **Critique Agent**: Feasibility analysis and risk assessment for the aggressive solution from the **Bold Proposer**.
3. **Reducer Agent**: Simplified, "less is more" approach focusing on the core functionality from a minimalistic standpoint, by simplifying the **Bold Proposer**'s design.

## Your Task

Review all three perspectives and synthesize a **balanced, consensus implementation plan** that:

1. **Incorporates the best ideas** from each perspective
2. **Resolves conflicts** between the proposals
3. **Balances innovation with pragmatism**
4. **Maintains simplicity** while not sacrificing essential features
5. **Addresses critical risks** identified in the critique
6. **Verifies documentation accuracy** - ensure proposals cite `docs/` for current command interfaces

## Input: Combined Report

Below is the combined report containing all three perspectives:

---

# Multi-Agent Debate Report: Unknown Feature

**Generated**: 2026-01-27 21:25

This document combines three perspectives from our multi-agent debate-based planning system:
1. **Report 1**: issue-6-bold-proposal.md
2. **Report 2**: issue-6-critique.md
3. **Report 3**: issue-6-reducer.md

---

## Part 1: issue-6-bold-proposal.md

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

---

## Part 2: issue-6-critique.md

# Proposal Critique: AI-Powered Quiz Generation with Bloom-Calibrated Difficulty

## Executive Summary

The proposal demonstrates solid research grounding and architectural alignment with existing codebase patterns. However, several critical issues undermine its claimed DRY benefits: **Stage 1 knowledge extraction cannot be directly reused from CheatsheetUseCase** due to the method being a private async method (`_extract_knowledge_items`) that is not accessible outside the class. The three-stage pipeline with Bloom's taxonomy calibration is technically sound but introduces significant cost complexity (up to 3x LLM calls per item) that may not be justified for all use cases. The 1410 LOC estimate is realistic but the spaced repetition features represent scope creep beyond the original "Quiz" feature request.

## Files Checked

**Documentation and codebase verification:**
- `/Users/EthanLee/Desktop/CourseSubtitle/CLAUDE.md`: Verified Clean Architecture structure with 4 layers
- `/Users/EthanLee/Desktop/CourseSubtitle/README.md`: Verified Quiz listed as high-priority roadmap item (line 106)
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/cheatsheet.py`: Verified two-stage LLM pipeline, **found `_extract_knowledge_items` is a private async method (line 196-252)**
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/dto/cheatsheet.py`: Verified `KnowledgeItem` dataclass structure (line 17-35)
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/interfaces/parallel.py`: Verified `ParallelGroup` is a **Literal type with fixed values** - does not include "quiz_questions"
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/prompts/registry.py`: Verified `BasePromptBuilder` pattern and `create_default_registry()` factory
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/di/container.py`: Verified DI wiring patterns
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/interfaces/llm_provider.py`: Verified `LLMProviderProtocol` interface

## Assumption Validation

### Assumption 1: Stage 1 can directly reuse CheatsheetUseCase._extract_knowledge_items()

- **Claim**: "Stage 1 extraction can literally call existing cheatsheet extraction logic"
- **Reality check**: The method `_extract_knowledge_items()` in `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/cheatsheet.py:196-252` is:
  1. A **private method** (prefixed with `_`)
  2. An **async method** requiring `await`
  3. Returns `list[KnowledgeItem]` which is tightly coupled to cheatsheet's DTO
- **Status**: INVALID
- **Evidence**:
  ```python
  # Line 196-202 of cheatsheet.py
  async def _extract_knowledge_items(
      self,
      context: str,
      language: str,
      subject_type: str,
      user_instruction: str,
  ) -> list[KnowledgeItem]:
  ```
  This method cannot be called from QuizUseCase without either:
  - Refactoring to expose it publicly (violates current encapsulation)
  - Creating a dependency on CheatsheetUseCase (creates coupling)
  - Duplicating the logic (violates DRY)

### Assumption 2: ParallelGroup can be extended with "quiz_questions"

- **Claim**: Proposal uses `group="quiz_questions"` in parallel runner calls
- **Reality check**: `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/interfaces/parallel.py:13-18` defines:
  ```python
  ParallelGroup = Literal[
      "subtitle_batches",
      "timeline_units",
      "note_parts",
      "voiceover_tts",
  ]
  ```
  This is a **Literal type** - adding new groups requires modifying the interface definition.
- **Status**: QUESTIONABLE
- **Evidence**: The proposal does not mention modifying `ParallelGroup` to include "quiz_questions". This would require changes to the interface file and potentially the infrastructure `ThreadPoolParallelRunner`.

### Assumption 3: PS4 prompting strategy achieves 81.37% quality

- **Claim**: "PS4 (Chain-of-Thought + skill definitions + examples) achieving 81.37% high-quality questions"
- **Reality check**: The cited arXiv paper (2408.04394) was tested on specific datasets and domains. Quality rates are highly dependent on:
  - Domain (educational vs. general knowledge)
  - Language (English-centric research)
  - LLM model used
- **Status**: QUESTIONABLE
- **Evidence**: The 81.37% figure is from controlled academic experiments. Real-world performance on video lecture content in Chinese may differ significantly.

### Assumption 4: KnowledgeItem is suitable for quiz generation

- **Claim**: Reuse `KnowledgeItem` structure from cheatsheet
- **Reality check**: The `KnowledgeItem` dataclass (line 17-35 of `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/dto/cheatsheet.py`) has:
  ```python
  category: str  # formula | definition | condition | algorithm | constant | example
  content: str
  criticality: str  # high | medium | low
  tags: list[str]
  ```
  This structure is optimized for **cheatsheet rendering** (dense information display), not **question generation** (testing cognitive skills).
- **Status**: QUESTIONABLE
- **Evidence**: Quiz questions may need:
  - Source text context (for distractor generation)
  - Relationships between concepts (for comparison questions)
  - Prerequisite knowledge markers
  - Original timestamp references (for video navigation)

## Technical Feasibility Analysis

### Integration with Existing Code

**Compatibility**: PARTIAL

- **LLMProviderProtocol**: VALID - Quiz can use existing LLM infrastructure via `self._llm.complete()`
- **PromptRegistry**: VALID - Can add new builders following `BasePromptBuilder` pattern
- **Storage Pattern**: VALID - `FsQuizStorage` can follow `FsCheatsheetStorage` pattern
- **API Routes**: VALID - Can follow existing Flask Blueprint pattern in `/presentation/api/routes/`
- **DI Container**: VALID - Can add `quiz_usecase` following existing patterns

**Conflicts**:
1. **ParallelGroup**: Requires modification to Literal type definition
2. **KnowledgeItem Coupling**: If quiz imports from cheatsheet.dto, creates cross-feature coupling

### Complexity Analysis

**Is this complexity justified?**

The three-stage pipeline is architecturally sound but introduces significant complexity:

1. **Stage 1 (Knowledge Extraction)**: Necessary, but claiming DRY reuse is misleading
2. **Stage 2 (Question Generation)**: Core value - justified
3. **Stage 3 (Distractor Synthesis)**: Separate LLM call for distractors is **questionable**

**Simpler alternatives overlooked:**

1. **Two-Stage Alternative**: Generate questions WITH distractors in a single prompt. Modern LLMs can handle "generate 4 MCQ questions with plausible distractors" without separate distractor synthesis.

2. **Direct Generation**: Skip knowledge extraction entirely. Directly prompt: "Given this lecture content, generate quiz questions at [Bloom level]". Many successful quiz generation systems use single-stage approaches.

3. **Template-Based Questions**: For "remember" level (definitions, formulas), use deterministic template generation instead of LLM calls.

## Risk Assessment

### HIGH Priority Risks

1. **Cost Explosion**
   - Impact: 3 LLM calls per knowledge item (extraction + question + distractor) could result in 30+ API calls for a single video lecture
   - Likelihood: HIGH
   - Mitigation: Make distractor synthesis optional; batch multiple items per LLM call; consider single-stage generation for simpler question types

2. **DRY Violation Disguised as DRY**
   - Impact: If `_extract_knowledge_items` cannot be reused, the proposal's core DRY claim fails
   - Likelihood: HIGH (confirmed by code analysis)
   - Mitigation: Either refactor `CheatsheetUseCase` to expose extraction as a shared service, or acknowledge duplication and create a shared `KnowledgeExtractor` class

3. **Bloom Level Drift**
   - Impact: LLM-generated questions may not align with intended Bloom level; users may not understand or correctly configure Bloom levels
   - Likelihood: MEDIUM
   - Mitigation: Simplify to 3 levels (Basic/Intermediate/Advanced) instead of full 6-level Bloom taxonomy

### MEDIUM Priority Risks

1. **Spaced Repetition Scope Creep**
   - Impact: SM-2 algorithm, session tracking, and adaptive difficulty are features unto themselves, adding ~300 LOC+ to an already large feature
   - Likelihood: HIGH (explicitly in proposal)
   - Mitigation: Phase 2 feature; remove from initial implementation

2. **JSON Parsing Fragility**
   - Impact: Complex nested structures (questions with distractors with reasoning) increase parse failure risk
   - Likelihood: MEDIUM
   - Mitigation: Use existing `parse_llm_json()` utility; design simpler output schemas

3. **Chinese Language Quality**
   - Impact: Bloom's taxonomy research is English-centric; Chinese question generation quality is unvalidated
   - Likelihood: MEDIUM
   - Mitigation: Include Chinese language examples in prompts; user testing with native speakers

### LOW Priority Risks

1. **TwinStar Review Overhead**
   - Impact: Optional dual-LLM review doubles cost for marginal quality improvement
   - Likelihood: LOW (marked as optional)
   - Mitigation: Keep as Phase 3 enhancement

## Critical Questions

These must be answered before implementation:

1. **DRY Strategy**: Will Stage 1 duplicate `_extract_knowledge_items` logic, or will we refactor to create a shared `KnowledgeExtractor` service that both CheatsheetUseCase and QuizUseCase can use?

2. **Scope Confirmation**: Is spaced repetition (SM-2 scheduling, adaptive sessions) in scope for v1, or should Quiz focus solely on generation?

3. **Cost Budget**: What is the acceptable LLM cost per quiz generation? This determines whether 3-stage vs 2-stage vs 1-stage approach is appropriate.

4. **Bloom Simplification**: Should we use full 6-level Bloom taxonomy, or simplify to 3 levels (Remember/Understand/Apply) for better user experience?

5. **Question Types**: Is MCQ sufficient for v1, or must True/False and Fill-in-blank be included?

## Recommendations

### Must Address Before Proceeding

1. **Create Shared KnowledgeExtractor**
   - Extract knowledge extraction logic from `CheatsheetUseCase` into a shared `KnowledgeExtractor` class
   - Both `CheatsheetUseCase` and `QuizUseCase` depend on this shared service
   - This achieves true DRY compliance
   - **Estimated additional LOC**: ~80 (refactoring) + 0 (quiz reuses)

2. **Add "quiz_questions" to ParallelGroup**
   - Modify `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/interfaces/parallel.py` line 13-18
   - **Required change**:
     ```python
     ParallelGroup = Literal[
         "subtitle_batches",
         "timeline_units",
         "note_parts",
         "voiceover_tts",
         "quiz_questions",  # Add this
     ]
     ```

3. **Remove Spaced Repetition from v1**
   - `QuizSession` with SM-2 scheduling is out of scope for initial Quiz feature
   - Reduces DTOs from ~120 LOC to ~80 LOC
   - Reduces API routes from ~180 LOC to ~120 LOC

### Should Consider

1. **Combine Stages 2 and 3**
   - Generate questions WITH distractors in single prompt
   - Reduces LLM calls by 33%
   - Example prompt: "Generate MCQ with 4 options where the correct answer is [A] and distractors target these misconceptions: [misconception list]"

2. **Simplify Bloom to 3 Levels**
   - Map 6 levels to: Easy (remember/understand), Medium (apply/analyze), Hard (evaluate/create)
   - Better UX for non-educators
   - Easier to validate

3. **Use Existing Prompts Pattern**
   - Cheatsheet uses `build_*_prompts()` functions, NOT the registry
   - Consider whether quiz needs registry integration or simpler function-based prompts

### Nice to Have

1. **Question Bank Deduplication**
   - Detect semantically similar questions across regenerations
   - Requires embedding-based similarity (new dependency)

2. **Difficulty Calibration via User Feedback**
   - Track correct/incorrect answers to adjust difficulty scores
   - Requires session tracking (Phase 2)

## Overall Assessment

**Feasibility**: HIGH - technically achievable with existing infrastructure

**Complexity**: OVER-ENGINEERED
- Three-stage pipeline where two stages may suffice
- Spaced repetition is scope creep
- Full Bloom taxonomy is over-complex for typical users

**Readiness**: NEEDS REVISION

**Bottom line**: The proposal is architecturally sound but overpromises on DRY reuse. The claimed "70% reuse" is closer to **30-40% actual reuse** once we account for:
1. Private method extraction needing refactoring
2. KnowledgeItem needing quiz-specific extensions
3. ParallelGroup needing modification
4. Spaced repetition being out of scope

**Recommended path forward**:
1. Accept two-stage approach (extraction + generation-with-distractors) instead of three stages
2. Create shared `KnowledgeExtractor` service for true DRY
3. Defer spaced repetition to Phase 2
4. Simplify Bloom to 3 levels
5. Reduce LOC estimate to ~900-1000 (from 1410)

---

## Part 3: issue-6-reducer.md

# Simplified Proposal: Quiz Generation (Single-Stage LLM)

## Simplification Summary

This proposal reduces the bold three-stage pipeline (Knowledge Extraction, Question Generation, Distractor Synthesis) to a **single-stage LLM call** that generates complete quiz questions directly. By removing Bloom's taxonomy calibration, misconception modeling, TwinStar review, and the intermediate extraction stage, we achieve approximately 65% LOC reduction while retaining core functionality. The existing cheatsheet pattern provides a proven template for two-stage pipelines if needed later.

## Files Checked

**Documentation and codebase verification:**
- `/Users/EthanLee/Desktop/CourseSubtitle/CLAUDE.md`: Verified project architecture (Clean Architecture layers)
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/cheatsheet.py`: Verified two-stage LLM pipeline pattern (326 LOC total)
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/dto/cheatsheet.py`: Verified DTO patterns (123 LOC)
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/interfaces/cheatsheet.py`: Verified storage protocol pattern (51 LOC)
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/prompts/cheatsheet.py`: Verified prompt builder pattern (118 LOC)
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/infrastructure/repositories/fs_cheatsheet_storage.py`: Verified filesystem storage pattern (119 LOC)
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/api/routes/cheatsheet.py`: Verified API route pattern (127 LOC)
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/di/container.py`: Verified DI container wiring pattern
- `/Users/EthanLee/Desktop/CourseSubtitle/docs/README.md`: Verified no existing quiz documentation

## Core Problem Restatement

**What we are actually solving:**
Generate multiple-choice quiz questions from lecture content (subtitles) to help students test their understanding.

**What we are NOT solving:**
- Bloom's taxonomy cognitive level calibration (premature optimization)
- Sophisticated misconception-based distractor synthesis (research-grade complexity)
- Dual-LLM validation (TwinStar review - speculative quality concern)
- Multi-source knowledge extraction (cheatsheet already does this)
- Adaptive difficulty levels (can add later if needed)

## Complexity Analysis

### Removed from Original

1. **Three-Stage Pipeline (reduced to one stage)**
   - Why it is unnecessary: A single well-crafted prompt can generate complete MCQ questions with distractors directly. The "extraction" stage duplicates what cheatsheet already does.
   - Impact of removal: Simpler code, faster generation, lower API cost
   - Can add later if needed: Yes, can upgrade to two-stage if quality issues arise

2. **Bloom's Taxonomy Calibration**
   - Why it is unnecessary: Research-grade feature. Most users want "good questions," not pedagogically-calibrated cognitive levels.
   - Impact of removal: None for MVP. Can hint at difficulty without formal Bloom categorization.
   - Can add later if needed: Yes, add to prompt if user demand arises

3. **PS4 Prompting Strategy with CoT**
   - Why it is unnecessary: Over-engineering. Standard prompting with clear examples achieves acceptable quality.
   - Impact of removal: Minimal - simpler prompt, still effective
   - Can add later if needed: Yes, enhance prompt if quality issues

4. **Misconception-based Distractor Synthesis**
   - Why it is unnecessary: "Student choice prediction" requires training data we do not have. LLM can generate plausible distractors without this.
   - Impact of removal: Distractors may be slightly less pedagogically optimal
   - Can add later if needed: Yes, but requires user research first

5. **TwinStar Dual-LLM Review**
   - Why it is unnecessary: Speculative quality concern. No evidence single-pass generation is insufficient.
   - Impact of removal: 50% fewer LLM calls, faster generation
   - Can add later if needed: Yes, add as optional "high-quality mode" later

6. **Separate Knowledge Extraction Stage**
   - Why it is unnecessary: Cheatsheet already extracts knowledge. Quiz can reuse cheatsheet output OR generate directly from subtitles.
   - Impact of removal: DRY - reuses existing functionality
   - Can add later if needed: Already exists in cheatsheet

### Retained as Essential

1. **Single-Stage Quiz Generation**
   - Why it is necessary: Core functionality - must generate questions
   - Simplified approach: One LLM call with structured JSON output

2. **Multiple-Choice Format**
   - Why it is necessary: Most universally useful format
   - Simplified approach: Fixed format (question + 4 options + correct answer + explanation)

3. **Configurable Question Count**
   - Why it is necessary: User flexibility
   - Simplified approach: Simple integer parameter (default: 5)

4. **Storage and Retrieval**
   - Why it is necessary: Avoid regeneration, allow editing
   - Simplified approach: Follow cheatsheet pattern exactly

### Deferred for Future

1. **Difficulty Levels**
   - Why we can wait: Simple prompt hint suffices for MVP
   - When to reconsider: If users request difficulty selection

2. **Question Types (fill-blank, true/false)**
   - Why we can wait: MCQ covers 80% of use cases
   - When to reconsider: User feedback requesting variety

3. **Cheatsheet Integration (reuse extracted knowledge)**
   - Why we can wait: Direct subtitle generation works; optimization can come later
   - When to reconsider: If generation quality is poor or API costs too high

## Minimal Viable Solution

### Core Components

1. **QuizUseCase**: `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/quiz.py`
   - Files: 1 file
   - Responsibilities: get(), save(), generate() - mirror cheatsheet pattern exactly
   - LOC estimate: ~120 (vs. original 350)
   - Simplifications applied:
     - Single-stage generation (no extraction step)
     - No Bloom calibration
     - No distractor synthesis stage
     - Reuse `_load_context` pattern from cheatsheet

2. **Quiz DTOs**: `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/dto/quiz.py`
   - Files: 1 file
   - Responsibilities: QuizQuestion, QuizResult, GenerateQuizRequest
   - LOC estimate: ~60 (vs. original 120)
   - Simplifications applied:
     - No BloomLevel enum
     - No DistractorAnalysis
     - Simple dataclasses only

3. **Quiz Prompts**: `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/prompts/quiz.py`
   - Files: 1 file
   - Responsibilities: Single prompt builder function
   - LOC estimate: ~60 (vs. original 180)
   - Simplifications applied:
     - One prompt function instead of three
     - No Bloom taxonomy instructions
     - No misconception modeling

4. **Quiz Storage**: Following exact cheatsheet pattern
   - Interface: `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/interfaces/quiz.py` (~30 LOC)
   - Implementation: `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/infrastructure/repositories/fs_quiz_storage.py` (~80 LOC)
   - Simplifications: Copy cheatsheet pattern, change namespace to "quiz"

5. **Quiz API Route**: `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/api/routes/quiz.py`
   - Files: 1 file
   - Responsibilities: GET, POST, POST /generate endpoints
   - LOC estimate: ~90 (vs. original 180)
   - Simplifications applied:
     - Mirror cheatsheet route exactly
     - Fewer validation rules (no Bloom level validation)

### Implementation Strategy

**Approach**: Clone cheatsheet pattern, simplify to single-stage

**Key simplifications:**
1. One LLM call per generation (not three stages)
2. No intermediate data structures (KnowledgeItem equivalent not needed)
3. Direct JSON output from LLM (question array)
4. Copy-paste cheatsheet storage pattern with namespace change

### No External Dependencies

No new dependencies required. Uses existing:
- LLMProviderProtocol (already in use)
- PathResolverProtocol (already in use)
- SubtitleStorageProtocol (already in use)

## Comparison with Original

| Aspect | Original Proposal | Simplified Proposal |
|--------|------------------|---------------------|
| Total LOC | ~1410 | ~500 (65% reduction) |
| Files | 6+ files | 5 files |
| LLM Calls | 3 per generation | 1 per generation |
| Dependencies | None | None |
| Complexity | High | Low |
| Pipeline Stages | 3 | 1 |
| Bloom Taxonomy | Yes | No (defer) |
| Distractor Modeling | Yes | No (LLM handles) |
| TwinStar Review | Optional | No (defer) |

## What We Gain by Simplifying

1. **Faster implementation**: 500 LOC vs. 1410 LOC means ~1/3 the development time
2. **Easier maintenance**: Single-stage pipeline is easier to debug and modify
3. **Lower risk**: Fewer moving parts, fewer potential failure points
4. **Clearer code**: Direct mapping from request to response, no intermediate transformations
5. **Lower API cost**: 1 LLM call vs. 3 per generation (66% cost reduction)
6. **Faster generation**: No sequential stage dependencies

## What We Sacrifice (and Why It Is OK)

1. **Bloom's Taxonomy Calibration**
   - Impact: Questions may not be perfectly distributed across cognitive levels
   - Justification: Users want "good questions," not pedagogical precision; YAGNI applies
   - Recovery plan: Add difficulty hint parameter to prompt; full Bloom later if demanded

2. **Sophisticated Distractor Quality**
   - Impact: Distractors may be slightly less "pedagogically optimal"
   - Justification: Modern LLMs generate reasonable distractors without special prompting
   - Recovery plan: Enhance prompt with misconception hints if quality complaints arise

3. **Dual-LLM Validation**
   - Impact: No automated quality assurance
   - Justification: No evidence single-pass is insufficient; user can regenerate if unhappy
   - Recovery plan: Add optional validation stage if quality issues reported

4. **Multi-Stage Knowledge Reuse**
   - Impact: Cannot share extracted knowledge with cheatsheet
   - Justification: Cheatsheet already has this; quiz can call cheatsheet first if needed
   - Recovery plan: Add optional `use_cheatsheet_knowledge` parameter later

## Implementation Estimate

**Total LOC**: ~500 (Low-Medium complexity)

**Breakdown**:
- `use_cases/quiz.py`: ~120 LOC
- `use_cases/dto/quiz.py`: ~60 LOC
- `use_cases/prompts/quiz.py`: ~60 LOC
- `use_cases/interfaces/quiz.py`: ~30 LOC
- `infrastructure/repositories/fs_quiz_storage.py`: ~80 LOC
- `presentation/api/routes/quiz.py`: ~90 LOC
- DI container additions: ~20 LOC
- Documentation: ~40 LOC

## Red Flags Eliminated

These over-engineering patterns were removed:

1. **Premature Abstraction (Three-Stage Pipeline)**: A single-stage pipeline is sufficient until proven otherwise. Adding stages is easier than removing them.

2. **Speculative Feature (Bloom's Taxonomy)**: No user has requested cognitive level calibration. Solve actual problems first.

3. **Research-Grade Complexity (Misconception Modeling)**: Requires training data and research validation we do not have. LLM distractors are "good enough."

4. **Unnecessary Indirection (TwinStar Review)**: Dual-LLM validation adds latency and cost without proven benefit. Users can regenerate if quality is poor.

5. **Premature Optimization (PS4 Prompting Strategy)**: Complex prompting strategies are optimization; start simple, measure, then optimize.

---

**Bottom Line**: Generate quiz questions with one LLM call, store as JSON, expose via API. Follow cheatsheet pattern exactly. Add sophistication only when user feedback justifies it.

---

## Next Steps

This combined report will be reviewed by an external consensus agent (Codex or Claude Opus) to synthesize a final, balanced implementation plan.

---

## Output Requirements

Generate a final implementation plan that follows the plan-guideline structure and rules:
- **Design-first TDD ordering**: Documentation → Tests → Implementation (never invert).
- **Use LOC estimates only** (no time-based estimates).
- **Be concrete**: cite exact repo-relative files/sections; avoid vague audit steps.
- **Include dependencies** for each step so ordering is enforced.
- **For every step, list correspondence** to documentation and test cases (what it updates, depends on, or satisfies).
- **If this is a bug fix**, include Bug Reproduction (or explicit skip reason).

```markdown
# Implementation Plan: Unknown Feature

## Consensus Summary

[2-3 sentences explaining the balanced approach chosen]

## Goal
[1-2 sentence problem statement]

**Success criteria:**
- [Criterion 1]
- [Criterion 2]

**Out of scope:**
- [What we're not doing]
- However, it it a good idea for future work?
  - If so, briefly describe it here. ✅ Good to have in the future: Briefly describe it in 1-2 sentences.
  - If not, explain why it's excluded. ❌ Not needed: Explain why it is a bad idea.

## Bug Reproduction
*(Optional - include only for bug fixes where reproduction was attempted)*

**Steps tried:**
- [Command or action performed]
- [Files examined]

**Observed symptoms:**
- [Error messages, test failures, unexpected behavior]

**Environment snapshot:**
- [Relevant file state, dependencies, configuration]

**Root cause hypothesis:**
- [Diagnosis based on observations]

**Skip reason** *(if reproduction not attempted)*:
- [Why reproduction was skipped]

**Unreproducible constraints** *(if reproduction failed)*:
- [What was tried and why it didn't reproduce]
- [Hypothesis for proceeding without reproduction]

## Codebase Analysis

**Files verified (docs/code checked by agents):**
- [File path 1]: [What was verified]
- [File path 2]: [What was verified]

**File changes:**

| File | Level | Purpose |
|------|-------|---------|
| `path/to/file1` | major | Significant changes description |
| `path/to/file2` | medium | Moderate changes description |
| `path/to/file3` | minor | Small changes description |
| `path/to/new/file` (new) | major | New file purpose (Est: X LOC) |
| `path/to/deprecated/file` | remove | Reason for removal |

**Modification level definitions:**
- **minor**: Cosmetic or trivial changes (comments, formatting, <10 LOC changed)
- **medium**: Moderate changes to existing logic (10-50 LOC, no interface changes)
- **major**: Significant structural changes (>50 LOC, interface changes, or new files)
- **remove**: File deletion

**Current architecture notes:**
[Key observations about existing code]

## Interface Design

**New interfaces:**
- Interface signatures and descriptions. Especially talk about:
  - Exposed functionalities to internal use or user usage
  - Internal implmentation based on the complexity
    - If it is less than 20 LoC, you can just talk about the semantics of the interface omit this
    - If it is with for loop and complicated conditional logics, put the steps here:
      - Step 1: Get ready for input
      - Step 2: Iterate over the input
        - Step 2.1: Check condition A
        - Step 2.2: Check condition B
        - Step 2.3: If condition A and B met, do X, if not go back to Step 2
        - Step 2.3: Return output based on conditionals
      - Step 3: Return final output
  - If any data structures or bookkeepings are needed, describe them here
    - What attributes are needed?
    - What are they recording?
    - Do they have any member methods associated?

**Modified interfaces:**
- [Before/after comparisons]
- It is preferred to have `diff` format if the change is less than 20 LoC:
```diff
- old line 1
- old line 2
+ new line 1
+ new line 2
```

**Documentation changes:**
- [Doc files to update with sections]

## Documentation Planning

**REQUIRED**: Explicitly identify all documentation impacts using these categories:

**High-level design docs (docs/):**
- `docs/workflows/*.md` — workflow and process documentation
- `docs/tutorial/*.md` — tutorial and getting-started guides
- `docs/architecture/*.md` — architectural design docs

**Folder READMEs:**
- `path/to/module/README.md` — module purpose and organization

**Interface docs:**
- Source file companion `.md` files documenting interfaces

Each document modifications should be as details as using `diff` format:
```diff
- Old document on interface(a, b, c)
+ New document on new_interface(a, b, c, d)
+ d handles the new feature by...
```

**Format:**
```markdown
## Documentation Planning

### High-level design docs (docs/)
- `docs/path/to/doc.md` — create/update [brief rationale]

### Folder READMEs
- `path/to/README.md` — update [what aspect]

### Interface docs
- `src/module/component.md` — update [which interfaces]
```

**Citation requirement:** When referencing existing command interfaces (e.g., `/ultra-planner`, `/issue-to-impl`), cite the actual `docs/` files (e.g., `docs/workflows/ultra-planner.md`, `docs/tutorial/02-issue-to-impl.md`) to ensure accuracy.

## Test Strategy

**Test modifications:**
- `test/file1` - What to test
  - Test case: Description
  - Test case: Description

**New test files:**
- `test/new_file` - Purpose (Estimated: X LOC)
  - Test case: Description
  - Test case: Description

**Test data required:**
- [Fixtures, sample data, etc.]

## Implementation Steps

**Step 1: [Documentation change]** (Estimated: X LOC)
- File changes
Dependencies: None
Correspondence:
- Docs: [What this step adds/updates]
- Tests: [N/A or what this enables]

**Step 2: [Test case changes]** (Estimated: X LOC)
- File changes
Dependencies: Step 1
Correspondence:
- Docs: [Which doc changes define these tests]
- Tests: [New/updated cases introduced here]

**Step 3: [Implementation change]** (Estimated: X LOC)
- File changes
Dependencies: Step 2
Correspondence:
- Docs: [Which doc behaviors are implemented here]
- Tests: [Which test cases this step satisfies]

If is preffered to put some implementation snippets here, if it is less than 20 LoC, use this format:
\`\`\`diff
- the code to be modified
+ the modified code
\`\`\`
where gives plan reviewer a quick idea of the implementation.

...

**Total estimated complexity:** X LOC ([Complexity level])
**Recommended approach:** [Single session / Milestone commits]
**Milestone strategy** *(only if large)*:
- **M1**: [What to complete in milestone 1]
- **M2**: [What to complete in milestone 2]
- **Delivery**: [Final deliverable]

## Success Criteria

- [ ] [Criterion 1]
- [ ] [Criterion 2]
- [ ] [Criterion 3]

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| [Risk 1] | [H/M/L] | [H/M/L] | [How to mitigate] |
| [Risk 2] | [H/M/L] | [H/M/L] | [How to mitigate] |

## Dependencies

[Any external dependencies or requirements]
```

## Evaluation Criteria

Your consensus plan should:

✅ **Be balanced**: Not too bold, not too conservative
✅ **Be practical**: Implementable with available tools/time
✅ **Be complete**: Include all essential components
✅ **Be clear**: Unambiguous implementation steps
✅ **Address risks**: Mitigate critical concerns from critique
✅ **Stay simple**: Remove unnecessary complexity per reducer
✅ **Correct measurement**: Use LOC estimates only; no time-based estimates
✅ **Accurate modification levels**: Every file must have correct level (minor/medium/major/remove)

❌ **Avoid**: Over-engineering, ignoring risks, excessive scope creep, vague specifications, or "audit the codebase" steps

## Final Privacy Note

As this plan will be published in a Github Issue, ensure no sensitive or proprietary information is included.

- No absolute paths from `/` or `~` or some other user-specific directories included
  - Use relative path from the root of the repo instead
- No API keys, tokens, or credentials
- No internal project names or codenames
- No personal data of any kind of users or developers
- No confidential business information
