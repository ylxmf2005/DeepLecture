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
