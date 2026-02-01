# Plan: Iteration Memory + Redis Compile Error Cache

## Two layers of agent memory

| Layer | Scope | Storage | Purpose |
|-------|-------|---------|---------|
| **Within-run** | Single `/api/run` request | Python list | Agent sees iteration history, avoids repeating mistakes |
| **Cross-run** | Persists across runs | Redis | Agent learns from past compile errors, skips LLM when a known fix exists |

---

## Part 1: In-Memory Iteration History (within-run)

### `backend/agent.py`

- Add `IterationRecord` dataclass: `iteration, lpips_score, lpips_improved, compile_error, critique_summary, agent_notes`
- Add `format_iteration_history(records) -> str` — produces condensed block:
  ```
  ITERATION HISTORY:
    Iter 1: LPIPS=0.4231 | Approach: soft particle grid with noise
    Iter 2: LPIPS=0.3892 [IMPROVED] | Approach: added glow
    Iter 3: LPIPS=0.3910 [WORSENED] | COMPILE ERROR: vec3 constructor...
  ```
- Modify `edit_shader()` — add `iteration_history: str | None` param, inject into prompt
- No change to `generate_initial_shader()` (iteration 0, no history)

### `backend/app.py`

- Accumulate `iteration_history: list[IterationRecord]` in the run loop
- Compute `lpips_improved` by comparing to previous score
- Pass formatted history to `edit_shader()` calls

---

## Part 2: Redis Compile Error Cache (cross-run)

### How it works

1. When a shader fails to compile, **before** calling the LLM:
   - Normalize the error (strip line numbers, extract error type)
   - Query Redis: "have we fixed this error type before?"
   - If yes → inject past fix examples into the `fix_compile_errors()` prompt as few-shot examples
   - If a cached fix applies directly → try it first, skip the LLM call entirely

2. When `fix_compile_errors()` produces a fix that **compiles successfully**:
   - Store the error→fix pair in Redis
   - Key: normalized error pattern (e.g. `"incompatible_types:vec3_constructor"`)
   - Value: `{error_msg, broken_snippet, fixed_snippet, timestamp}`
   - No TTL — these are permanent learnings (like shader_agent_note.txt, but automated)

### Error normalization

GLSL errors look like:
```
ERROR: 0:78: Incompatible types in initialization
ERROR: 0:79: Use of undeclared identifier 'm'
```

Normalization strips line numbers and extracts the category:
- `"Incompatible types in initialization"` → key: `glsl:incompatible_types`
- `"'*' does not operate on 'vec2' and 'mat2'"` → key: `glsl:operator_mismatch`
- `"Use of undeclared identifier"` → key: `glsl:undeclared_identifier`

### New file: `backend/error_cache.py` (~80 lines)

```
ErrorCache class:
  - __init__(redis_url) — connect to Redis, graceful fallback if unavailable
  - normalize_error(error_msg) -> str — strip line numbers, extract category
  - lookup(error_msg) -> list[dict] — find past fixes for this error type
  - store(error_msg, broken_shader, fixed_shader) — save successful fix
  - get_few_shot_examples(error_msg, limit=3) -> str — format past fixes for prompt injection
```

Graceful degradation: if Redis is down, the cache is a no-op. The system works exactly as it does today.

### Changes to `backend/agent.py`

- `fix_compile_errors()` gains `few_shot_examples: str | None` param
- If examples exist, inject them into the prompt:
  ```
  PAST FIXES FOR SIMILAR ERRORS:
  Example 1: "Incompatible types" was fixed by changing vec3(x.xy, y.xy) → vec3(x.xy, y.z)
  Example 2: ...
  ```

### Changes to `backend/app.py`

- Import `ErrorCache`, initialize once at startup
- In the compile error recovery path (lines 170-191):
  - Before calling `fix_compile_errors()`: query cache for examples
  - After a successful fix+render: store the error→fix pair

### Redis setup

- Add `redis` to `requirements.txt`
- Add `REDIS_URL=redis://localhost:6379/0` to `.env`
- Setup instructions: `brew install redis && brew services start redis`
- If `REDIS_URL` not set or Redis unavailable → cache silently disabled, zero impact on existing flow

---

## Files Modified

| File | What changes |
|------|-------------|
| `backend/agent.py` | Add `IterationRecord`, `format_iteration_history()`, modify `edit_shader()` and `fix_compile_errors()` signatures/prompts |
| `backend/app.py` | Accumulate history list, init `ErrorCache`, query/store on compile errors |
| `backend/error_cache.py` | **New file** — `ErrorCache` class with normalize/lookup/store/format |
| `requirements.txt` | Add `redis` |
| `.env` | Add `REDIS_URL` |

## Verification

1. **Within-run memory**: Run 3+ iterations, confirm agent notes reference previous attempts
2. **Redis cache**: Trigger a compile error, verify it's stored in Redis (`redis-cli KEYS "glsl:*"`)
3. **Cache hit**: Run again with a shader that triggers the same error type, verify cached examples appear in the fix prompt
4. **Graceful fallback**: Stop Redis, run the app, confirm it works identically to today (no crashes)
