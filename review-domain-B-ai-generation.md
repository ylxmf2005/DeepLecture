# Domain B: AI Generation Features — Correctness Review

**Reviewer:** Domain B Reviewer Agent
**Date:** 2026-02-06
**Scope:** Ask, Note, Quiz, Cheatsheet, Explanation, Fact Verification, Content
**Files Reviewed:** ~50 files across backend use cases, prompts, routes, frontend components, API clients, hooks

---

## Executive Summary

| Severity | Count |
|----------|-------|
| Critical | 2 |
| High     | 4 |
| Medium   | 7 |
| Low      | 5 |
| Info     | 4 |

Two **critical** bugs affect Quiz and Cheatsheet generation — they are fundamentally broken due to async/sync mismatches. Several high-severity issues include inconsistent LLM calling conventions, missing prompt injection protection in newer features, and a missing frontend API layer for Quiz. Overall, the Ask, Note, and Explanation features are well-implemented and production-ready, while Quiz and Cheatsheet have systemic issues that prevent them from working.

---

## CRITICAL Issues

### B-C1: Quiz and Cheatsheet Use Cases — Async/Sync Mismatch (Completely Broken)
**Files:** `use_cases/quiz.py`, `use_cases/cheatsheet.py`, `infrastructure/workers/task_queue.py`
**Severity:** Critical

Both `QuizUseCase.generate()` and `CheatsheetUseCase.generate()` are declared as `async def` and use `await self._llm.complete(...)`. However:

1. **`LLMProtocol.complete()` is synchronous** (`use_cases/interfaces/services.py:21`) — `await` on a non-awaitable will raise `TypeError: object str can't be used in 'await' expression` at runtime.

2. **`TaskManager._execute_task()` calls `item.callable(ctx)` synchronously** (`infrastructure/workers/task_queue.py:524`) — The task queue runs in a thread pool with no event loop. Even if the LLM call were async, the coroutine would never be awaited. The routes pass `async def _run_generation` (e.g., `quiz.py:98`, `cheatsheet.py:104`), which means `item.callable(ctx)` returns a **coroutine object** that is silently discarded.

3. **LLM calling convention mismatch:** Quiz and Cheatsheet call `self._llm.complete(system_prompt=..., user_prompt=...)` but `LLMProviderProtocol.get()` returns an `LLMProtocol` whose `complete(prompt, *, system_prompt=...)` expects `prompt` as the first positional argument, not `user_prompt`. This is a different calling convention from all other use cases (Ask, Note, Explanation) which correctly use `llm.complete(user_prompt, system_prompt=system_prompt)`.

**Impact:** Quiz and Cheatsheet generation will **always fail** at runtime. The task will be marked as failed with an opaque error.

**Fix:** Remove `async`/`await` from quiz/cheatsheet use cases, use the same synchronous `llm.complete(user_prompt, system_prompt=system_prompt)` pattern as Note/Ask/Explanation, and integrate with `PromptRegistry` instead of calling prompt builders directly.

---

### B-C2: Quiz and Cheatsheet Missing Prompt Registry Integration
**Files:** `use_cases/quiz.py`, `use_cases/cheatsheet.py`, `prompts/registry.py`
**Severity:** Critical

Quiz and Cheatsheet use cases call prompt builder functions **directly** (e.g., `build_cheatsheet_extraction_prompts(...)`, `build_quiz_generation_prompts(...)`) instead of going through the `PromptRegistry`. This means:

1. The user cannot select alternative prompt implementations for quiz/cheatsheet via the Settings UI.
2. The `prompts` parameter passed from the API route is completely ignored.
3. This violates the established architecture where all other AI features (Ask, Note, Explanation, Timeline) use `self._prompt_registry.get(func_id, impl_id)`.

Additionally, `create_default_registry()` in `prompts/registry.py` does **not** register any quiz or cheatsheet prompt builders, confirming this integration was never completed.

---

## HIGH Issues

### B-H1: Quiz — No Frontend API Client
**Files:** `frontend/lib/api/` (missing quiz.ts)
**Severity:** High

There is no `frontend/lib/api/quiz.ts` file. While `FlashcardTab.tsx` exists, it displays **vocabulary words** (from a local Zustand store), not AI-generated quiz items. There is no frontend component that:
- Calls the `GET /api/quiz/<content_id>` endpoint
- Calls the `POST /api/quiz/<content_id>/generate` endpoint
- Displays generated MCQ quiz items

The backend quiz routes (`presentation/api/routes/quiz.py`) exist and are properly implemented, but have no frontend consumer.

---

### B-H2: Quiz/Cheatsheet — Subtitle Loading Uses Wrong Protocol Method
**Files:** `use_cases/quiz.py:227-234`, `use_cases/cheatsheet.py:183-188`
**Severity:** High

Both quiz and cheatsheet `_load_context()` methods call:
```python
subtitle_result = self._subtitles.load(request.content_id)
```

But `SubtitleStorageProtocol.load()` expects two arguments: `(content_id, language)`. Calling it with just `content_id` will either:
- Raise `TypeError` (missing positional argument), or
- Return unexpected results if the protocol has a fallback

This is inconsistent with how Note and Ask use cases load subtitles — they use the shared `load_first_available_subtitle_segments()` helper which properly iterates candidate languages.

---

### B-H3: Cheatsheet/Quiz — No Prompt Injection Sanitization
**Files:** `use_cases/quiz.py`, `use_cases/cheatsheet.py`
**Severity:** High

Both quiz and cheatsheet use cases pass `user_instruction` directly into LLM prompts without any sanitization:
- Quiz: `user_instruction=request.user_instruction` → directly embedded in prompt
- Cheatsheet: `user_instruction=request.user_instruction` → directly embedded in prompt

Compare with Note/Ask which properly use `sanitize_question()` and `sanitize_learner_profile()` from `shared/prompt_safety.py`. The cheatsheet and quiz prompts embed user instructions like:
```python
f"Additional instructions: {user_instruction}"
```
This is vulnerable to prompt injection.

---

### B-H4: Fact Verification — ClaudeCodeProtocol Coupling
**Files:** `use_cases/fact_verification.py`, `use_cases/interfaces/fact_verification.py`
**Severity:** High

The fact verification use case depends on `ClaudeCodeProtocol` which invokes Claude Code CLI as a subprocess. This is a unique external dependency with several concerns:

1. **No timeout configuration** — `self._claude.run_verification(prompt)` has no timeout parameter in the use case, and the Claude Code subprocess can potentially run for a very long time (web search + multiple subagents).
2. **Prompt embeds subtitle text directly** without sanitization via `prompt_safety.py`.
3. **The prompt references "deeplecture-fact-verifier" subagent type** which must be pre-configured in the Claude Code environment — this is an implicit runtime dependency not validated anywhere.

---

## MEDIUM Issues

### B-M1: Ask — Hardcoded Response Language
**File:** `use_cases/prompts/ask.py:128-139`
**Severity:** Medium

`get_response_language()` always returns `"Simplified Chinese"`:
```python
def get_response_language() -> str:
    # TODO: Read from config or environment
    return "Simplified Chinese"
```

This hardcoded value affects both `ask_question()` and `summarize_context()`. Users cannot change the Q&A response language. The Note and Explanation use cases correctly accept a `language` parameter from the request.

---

### B-M2: Note — Silent Failure on Outline Parse Error
**File:** `use_cases/note.py:376-422`
**Severity:** Medium

`_parse_outline_json()` returns an empty list `[]` on parse failure, then `_build_outline()` returns `[]`, and `generate_note()` raises `ValueError("LLM did not return a usable note outline.")`. While this eventually surfaces an error, the original LLM output is only logged at WARNING level with a 200-char preview. For debugging production issues, the full raw LLM response should be logged (at DEBUG level at minimum).

---

### B-M3: Explanation — Concrete Type in Use Case Constructor
**File:** `use_cases/explanation.py:49`
**Severity:** Medium

The `ExplanationUseCase.__init__` parameter is typed as `FsExplanationStorage` (a concrete infrastructure class) instead of a protocol:
```python
explanation_storage: FsExplanationStorage
```
This violates the Dependency Inversion Principle. All other use cases correctly depend on protocol interfaces (e.g., `NoteStorageProtocol`, `AskStorageProtocol`).

---

### B-M4: AskTab — No User-Visible Error Toast
**File:** `frontend/components/features/AskTab.tsx:225-228`
**Severity:** Medium

When `askVideoQuestion()` fails, the error is logged but no `toast.error()` is shown. Instead, a fake assistant message is inserted: `"Sorry, I encountered an error while processing your request."`. While this informs the user, it differs from the established pattern (e.g., `useNoteGeneration.ts` uses `toast.error("Failed to start note generation")`). The fake message becomes a permanent part of the conversation, and if the conversation is saved to the backend, the error message is persisted forever.

---

### B-M5: ExplanationList — No Error Toast on Load Failure
**File:** `frontend/components/content/ExplanationList.tsx:47-48`
**Severity:** Medium

When `getExplanationHistory()` fails, the error is logged but no user feedback is given — no toast, no error state displayed. The user sees an empty list with no indication that loading failed.

---

### B-M6: Content Route — Stale Processing Reconciliation Only Covers 4 Features
**File:** `presentation/api/routes/content.py:78-89`
**Severity:** Medium

`_reconcile_stale_processing()` only checks `video`, `subtitle`, `enhance_translate`, and `timeline` features. It does not check note generation, cheatsheet, quiz, explanation, or fact verification. If these tasks are in "processing" state when the server restarts, they remain stuck forever.

---

### B-M7: CheatsheetTab/VerifyTab — SSE Retry Logic Duplicated
**Files:** `frontend/components/features/CheatsheetTab.tsx`, `frontend/components/features/VerifyTab.tsx`
**Severity:** Medium

Both components implement nearly identical SSE-triggered retry logic (detect refreshTrigger change while generating, retry up to 3 times with 1s delay). This ~40 lines of duplicated logic should be extracted into a shared hook (e.g., `useSSEGenerationState`) to prevent drift and reduce maintenance burden.

---

## LOW Issues

### B-L1: Quiz — validate_quiz_item Field Check Order
**File:** `use_cases/quiz.py:46-63`
**Severity:** Low

The `validate_quiz_item` function checks `options` count and `answer_index` range before checking if required fields exist. If `stem` is missing, the more confusing "answer_index must be 0-3" error could trigger first (if `answer_index` is also missing/wrong). Required field presence should be checked first for better error messages.

---

### B-L2: Note — Prompt Returns (user, system) but Registry Expects (user, system)
**File:** `use_cases/prompts/note.py:116`
**Severity:** Low

`build_note_outline_prompt()` returns `(user_prompt, system_prompt)` tuple, and the `NoteOutlineBuilder.build()` correctly maps this. However, `build_note_part_prompt()` also returns `(user_prompt, system_prompt)`. This is opposite to the convention in `ask.py` prompts where `get_ask_video_prompt()` returns a single system prompt. While not a bug (the builders handle it correctly), the inconsistent return conventions could confuse future maintainers.

---

### B-L3: Fact Verification — Missing `withLLMOverrides` in Frontend API
**File:** `frontend/lib/api/factVerification.ts:38-48`
**Severity:** Low

The `generateFactVerification()` API call does not use `withLLMOverrides()`, unlike all other AI generation API calls. This means the user's LLM model selection from Settings is not applied to fact verification.

---

### B-L4: ClaimCard — Confidence Display Without Context
**File:** `frontend/components/features/ClaimCard.tsx:88-90`
**Severity:** Low

The confidence score is displayed as a plain percentage (e.g., "85%") with only a `title="Confidence Score"` tooltip. Users may not understand what this percentage means. A small label or color-coded indicator would improve clarity.

---

### B-L5: Cheatsheet — `target_pages` Coercion
**File:** `presentation/api/routes/cheatsheet.py:100`
**Severity:** Low

`target_pages=target_pages or 2` — if `validate_positive_int` returns `0` (which it shouldn't, but the function name says "positive"), this would silently default to `2` instead of raising an error. The `or` pattern conflates `None` with `0`.

---

## INFO / Positive Observations

### B-I1: Excellent Prompt Injection Protection in Ask/Note
The `shared/prompt_safety.py` module provides comprehensive protection:
- Regex-based injection pattern detection (instruction override, role manipulation, delimiter injection)
- Input sanitization (length limits, control char stripping, whitespace normalization)
- Content wrapping with XML delimiters (`wrap_user_content`)
- Pre-configured sanitizers for different input types (`sanitize_question`, `sanitize_learner_profile`)

Ask and Note use cases consistently apply these protections.

### B-I2: Robust JSON Parsing in Note Use Case
The `shared/llm_json.py` module uses `json_repair` library for fault-tolerant JSON parsing. The Note use case's `_parse_outline_json()` has thorough validation: type checks, field presence, graceful fallbacks for missing fields, and sorting by part ID.

### B-I3: Well-Designed MarkdownRenderer
The `MarkdownRenderer` component provides:
- LaTeX math rendering (KaTeX)
- GFM tables support
- Seekable timestamp links (`[MM:SS]` → clickable)
- URL sanitization against `javascript:` attacks
- Dark mode support
- Memoization for performance

### B-I4: Good Frontend Security in ClaimCard
The `ClaimCard.tsx` component implements `getSafeUrl()` to validate evidence URLs, only allowing `http:` and `https:` protocols. External links use `target="_blank" rel="noopener noreferrer"`.

---

## Complete Chain Analysis

### Ask (Q&A) — ✅ Fully Working
```
Frontend (AskTab.tsx) → API (ask.ts) → Route (conversation.py) → UseCase (ask.py)
→ PromptRegistry → LLM.complete() → Storage → Response
```
- Input sanitization: ✅ (sanitize_question, sanitize_learner_profile, wrap_user_content)
- JSON parsing: N/A (free-text response)
- Error handling: ✅ (backend raises, frontend catches and shows inline message)
- Loading state: ✅ (animated dots indicator)
- Markdown rendering: ✅ (MarkdownRenderer with LaTeX + timestamps)

### Note Generation — ✅ Fully Working
```
Frontend (useNoteGeneration.ts) → API (notes.ts) → Route (note.py) → TaskManager
→ UseCase (note.py) → PromptRegistry → LLM.complete() → parallel_runner → Storage → SSE → Frontend
```
- Input sanitization: ✅ (sanitize_learner_profile, sanitize_question for instruction)
- JSON parsing: ✅ (parse_llm_json with json_repair)
- Error handling: ✅ (toast.error on failure, error placeholder per-part)
- Loading state: ✅ (SSE-driven, confirm dialog before overwrite)
- Markdown rendering: ✅ (MarkdownNoteEditor with Milkdown)

### Quiz Generation — ❌ Broken
```
Frontend: NO FRONTEND COMPONENT
Route (quiz.py) → TaskManager → UseCase (quiz.py) [async def!]
→ build_cheatsheet_extraction_prompts() [direct, no registry]
→ await self._llm.complete() [WILL FAIL - sync method cannot be awaited]
```
- Two independent critical failures: async/sync mismatch + missing frontend

### Cheatsheet Generation — ❌ Broken
```
Frontend (CheatsheetTab.tsx) → API (cheatsheet.ts) → Route (cheatsheet.py) → TaskManager
→ UseCase (cheatsheet.py) [async def!]
→ build_cheatsheet_extraction_prompts() [direct, no registry]
→ await self._llm.complete() [WILL FAIL - sync method cannot be awaited]
```
- Frontend exists and is well-built, but backend use case will always fail

### Explanation — ✅ Fully Working
```
Frontend (ExplanationList.tsx) → API (explanation.ts) → Route (explanation.py) → TaskManager
→ UseCase (explanation.py) → PromptRegistry → LLM.complete(image_path=...) → Storage → SSE → Frontend
```
- Input sanitization: ✅ (sanitize_learner_profile)
- Error handling: ✅ (RuntimeError wrapped, pending state in UI)
- Loading state: ✅ (pending entry with "Generating explanation..." text)
- Markdown rendering: ✅ (MarkdownRenderer)

### Fact Verification — ⚠️ Partially Working (untestable without Claude Code)
```
Frontend (VerifyTab.tsx) → API (factVerification.ts) → Route (fact_verification.py) → TaskManager
→ UseCase (fact_verification.py) → ClaudeCodeProtocol → parse_result → Storage → SSE → Frontend
```
- Input sanitization: ❌ (subtitle text not sanitized before embedding in prompt)
- JSON parsing: ✅ (structured parsing with validation, URL sanitization, verdict allowlist)
- Error handling: ✅ (SSE retry pattern in frontend)
- Loading state: ✅ (dedicated generating state with descriptive message)
- Frontend rendering: ✅ (ClaimCard with verdict badges, evidence expansion, safe URLs)

### Content Management — ✅ Fully Working
```
Frontend → API (content.ts) → Route (content.py) → UseCase (content.py) → Storage
```
- Pure CRUD, no AI generation involved
- Clean architecture with proper error handling

---

## Recommendations (Priority Order)

1. **[CRITICAL]** Fix quiz.py and cheatsheet.py: Remove async/await, align with synchronous LLM calling convention, integrate with PromptRegistry
2. **[CRITICAL]** Register quiz and cheatsheet prompt builders in `create_default_registry()`
3. **[HIGH]** Build frontend quiz component and API client
4. **[HIGH]** Fix subtitle loading in quiz/cheatsheet to use `load_first_available_subtitle_segments()`
5. **[HIGH]** Add prompt injection sanitization to quiz/cheatsheet user instructions
6. **[MEDIUM]** Make Ask response language configurable (remove hardcoded "Simplified Chinese")
7. **[MEDIUM]** Fix ExplanationUseCase to depend on protocol instead of concrete FsExplanationStorage
8. **[MEDIUM]** Extract shared SSE generation state hook from CheatsheetTab/VerifyTab
