---
name: code-review-expert
description: Performs a comprehensive, multi-dimensional code review of a GitHub pull request, producing structured findings with severity levels.
---

# Code Review Expert

Perform a structured, multi-dimensional review of a GitHub pull request. You review the PR diff across 7 dimensions — architecture, security, error handling, performance, code quality, removal candidates, and forge project conventions — and produce a prioritized report with actionable findings.

## Input

`$ARGUMENTS` is the PR URL or PR number (e.g., `https://github.com/org/repo/pull/123` or `123`).

If `$ARGUMENTS` is empty or missing, display this usage help and stop:

```
Usage: /code-review-expert <PR-URL-or-number>

Examples:
  /code-review-expert https://github.com/aiml-lighthouse/forge/pull/42
  /code-review-expert 42
```

---

## Severity Levels

| Level | Name | Description | Action |
|-------|------|-------------|--------|
| **P0** | Critical | Security vulnerability, data loss risk, correctness bug | Must block merge |
| **P1** | High | Logic error, significant design violation, performance regression | Should fix before merge |
| **P2** | Medium | Code smell, maintainability concern, minor design issue | Fix in this PR or create follow-up |
| **P3** | Low | Style, naming, minor suggestion | Optional improvement |

---

## Workflow

### Phase 1 — Gather PR Context

Run these commands to collect all necessary context:

```bash
# PR metadata
gh pr view $ARGUMENTS --json title,body,author,baseRefName,headRefName,additions,deletions,changedFiles,labels,state,reviews

# Full diff
gh pr diff $ARGUMENTS

# Changed file list
gh pr diff $ARGUMENTS --name-only
```

**Large diff handling (>3000 lines changed):**
- Warn the user: "This is a large PR (N lines). Prioritizing core source files."
- Prioritize files matching `src/**/*.py` and `tests/**/*.py` first
- Deprioritize generated files, lock files, config/data files
- Review remaining files in a second pass if the user requests it

**Reading full file context:**
- For files where the diff alone is insufficient (e.g., a method change where you need to understand the class), read the full file using the Read tool
- Always read full files when reviewing changes to: class hierarchies, function signatures used elsewhere, workflow/graph definitions, prompt templates

---

### Phase 2 — Multi-Dimensional Review

Review the diff across all 7 dimensions. For each finding, record the file path, line number (from the diff), severity, and a concrete fix suggestion.

#### Dimension 1: Architecture & Design (SOLID for Python)

**Single Responsibility (SRP)**
- File owns unrelated concerns (e.g., HTTP + DB + domain rules in one file)
- Large class/module with low cohesion or multiple reasons to change
- Functions that orchestrate many unrelated steps
- God objects that know too much about the system
- Ask: "What is the single reason this module would change?"

**Open/Closed (OCP)**
- Adding behavior requires editing many `if/elif` chains or match blocks
- Feature growth requires modifying core logic rather than extending
- No plugin/strategy/hook points for variation
- Ask: "Can I add a new variant without touching existing code?"

**Liskov Substitution (LSP)**
- Subclass checks for concrete type or raises for base method
- Overridden methods weaken preconditions or strengthen postconditions
- Subclass ignores or no-ops parent behavior
- Ask: "Can I substitute any subclass without the caller knowing?"

**Interface Segregation (ISP)**
- ABCs/Protocols with many methods, most unused by implementers
- Callers depend on broad interfaces for narrow needs
- Empty/stub implementations of protocol methods
- Ask: "Do all implementers use all methods?"

**Dependency Inversion (DIP)**
- High-level logic depends on concrete I/O, storage, or network types
- Hard-coded implementations instead of abstractions or injection
- Import chains that couple business logic to infrastructure
- Ask: "Can I swap the implementation without changing business logic?"

**Common code smells:**

| Smell | Signs |
|-------|-------|
| Long method | Function > 30 lines, multiple nesting levels |
| Feature envy | Method uses more data from another class than its own |
| Data clumps | Same group of parameters passed together repeatedly |
| Primitive obsession | Using strings/numbers instead of domain types (dataclasses, enums) |
| Shotgun surgery | One change requires edits across many files |
| Dead code | Unreachable or never-called code |
| Speculative generality | Abstractions for hypothetical future needs |
| Magic numbers/strings | Hardcoded values without named constants |

#### Dimension 2: Security & Reliability

**Injection risks:**
- `subprocess` calls with `shell=True` or unsanitized user input
- `eval()`, `exec()`, `compile()` with external data
- String formatting in SQL queries instead of parameterized queries
- `os.system()` usage

**Secret exposure:**
- API keys, tokens, or credentials in code/config/logs
- Secrets in git history or environment variables exposed to output
- Excessive logging of PII or sensitive payloads

**Unsafe deserialization:**
- `pickle.load()` / `pickle.loads()` on untrusted data
- `yaml.load()` without `Loader=yaml.SafeLoader` (use `yaml.safe_load()`)
- `marshal.loads()` on untrusted input

**Path traversal:**
- User input in file paths without sanitization (`../` attacks)
- `os.path.join()` with user-controlled segments without validation

**Race conditions (threadpool-aware):**
- Multiple threads accessing shared mutable state without locks
- Check-then-act patterns (`if exists: use`) without atomic operations
- Read-modify-write without synchronization
- Global/module-level mutable state modified in threadpool workers
- Ask: "What happens if two threads hit this code simultaneously?"

**Resource leaks:**
- File/network handles opened without `with` statement (context manager)
- Missing `finally` blocks for cleanup
- Unbounded collections growing without limit
- Missing timeouts on external calls (HTTP, subprocess)

**Data integrity:**
- Missing input validation at system boundaries
- Partial writes or inconsistent state updates
- Missing idempotency for retryable operations

#### Dimension 3: Error Handling & Robustness

- **Bare except**: `except:` or `except Exception:` catching too broadly
- **Swallowed exceptions**: Empty except blocks or catch-and-log-only without re-raising
- **Missing error handling**: No try/except around I/O, network calls, file operations, JSON parsing
- **Error information leakage**: Internal details, stack traces, or file paths exposed in user-facing output
- **Error chaining**: Missing `from` in `raise NewError() from original` (loses traceback context)
- **Boundary conditions**: None/null handling, empty collections, division by zero, off-by-one errors
- **Type safety**: Missing type hints on public APIs, `Any` overuse, unchecked `cast()` calls

**Questions to ask:**
- "What happens when this operation fails?"
- "Will the caller know something went wrong?"
- "Is there enough context to debug this error in production?"

#### Dimension 4: Performance & Scalability

- **Algorithmic complexity**: O(n^2) or worse where O(n) or O(n log n) is possible
- **N+1 patterns**: Loop making an API/DB/LLM call per item instead of batching
- **Memory issues**: Loading large files entirely into memory, unbounded list growth, string concatenation in loops (use `"".join()`)
- **Missing caching**: Repeated expensive computations (LLM calls, file reads, embedding lookups) with same inputs
- **Blocking I/O**: Synchronous I/O in async context, missing threadpool for CPU-bound work
- **Unnecessary recomputation**: Regex compilation in loops (`re.compile` outside), repeated JSON parsing

**Questions to ask:**
- "How does this behave with 10x/100x data?"
- "Can this be batched instead of one-by-one?"
- "Is this result cacheable?"

#### Dimension 5: Code Quality & Maintainability

- **Dead code**: Unreachable branches, unused imports, commented-out code, unused variables
- **DRY violations**: Same logic repeated in multiple places; should be extracted to a shared function
- **Naming clarity**: Vague names (`data`, `result`, `tmp`, `x`), misleading names, inconsistent naming style
- **Function complexity**: Functions doing too many things, deep nesting (>3 levels), excessive parameters (>5)
- **Missing tests**: New logic without corresponding test coverage, modified logic without updated tests
- **Magic numbers/strings**: Hardcoded values that should be named constants or config

**Do NOT flag:**
- Formatting issues (trust `ruff` via `make lint` / `make format`)
- Import ordering (handled by `ruff`)
- Line length (handled by `ruff`)

#### Dimension 6: Removal Candidates

Identify code in the diff that introduces or perpetuates:
- Deprecated patterns or APIs
- Unused dependencies or imports
- Redundant abstractions (wrappers that add no value)
- Dead features or unreachable code paths
- Feature-flagged code that has been fully rolled out

Classify each as:
- **Safe delete now**: No active consumers, can remove in this PR
- **Defer with plan**: Needs migration or stakeholder sign-off; provide concrete follow-up steps

#### Dimension 7: Forge Project-Specific Checks

Apply the project conventions from AGENTS.md:

| Convention | What to flag |
|------------|--------------|
| **Package management** | `pip install`, `python script.py`, `python -m module` instead of `uv run`, `uv add`, `uv sync` |
| **CLI framework** | `argparse` instead of `click` |
| **Module naming** | Utilities not named `*_utils.py`, clients not named `*_client.py`, preprocessing not named `*_preprocessing.py` |
| **Parallelization** | Raw `threading` or `multiprocessing` for LLM calls instead of threadpool |
| **Frontend tooling** | `npm`, `node`, `yarn`, `pnpm` instead of `bun`; `express` instead of `Bun.serve()` |
| **Testing** | `python -m pytest` instead of `uv run pytest` or `make test` |
| **DRY principle** | Copy-pasted logic that should be a shared utility |

---

### Phase 3 — Structured Report

Output the review in this format:

```markdown
## Code Review: [PR Title]

**PR**: #[number] by [author]
**Branch**: [head] -> [base]
**Changes**: +[additions] -[deletions] across [N] files

---

### Summary

[1-3 sentence summary of the PR's purpose and scope]

**Verdict**: [APPROVE | REQUEST_CHANGES | COMMENT]

---

### Findings

#### P0 - Critical
(none found — or numbered list)

#### P1 - High
1. **[file:line]** Brief title
   - **Issue**: Description of the problem
   - **Impact**: What could go wrong
   - **Suggestion**: Concrete fix or approach

#### P2 - Medium
2. **[file:line]** Brief title
   - **Issue**: ...
   - **Suggestion**: ...

#### P3 - Low
3. **[file:line]** Brief title
   - **Suggestion**: ...

---

### Positive Observations

- [What the PR does well — always include at least 2-3 items]
- [Good patterns, thorough tests, clean design, etc.]

---

### Statistics

| Dimension | Findings |
|-----------|----------|
| Architecture & Design | N |
| Security & Reliability | N |
| Error Handling | N |
| Performance | N |
| Code Quality | N |
| Removal Candidates | N |
| Forge Conventions | N |
| **Total** | **N** |

| Severity | Count |
|----------|-------|
| P0 Critical | N |
| P1 High | N |
| P2 Medium | N |
| P3 Low | N |

---

> Generated by `/code-review-expert` in forge
```

**Numbering**: Continue numbering across severity sections (P0 #1-2, P1 #3-5, P2 #6-8, etc.) for easy reference.

**Clean review**: If no issues found, explicitly state what was checked and any areas not covered (e.g., "Did not verify database migrations" or "Integration test coverage not assessed").

---

### Phase 4 — Offer Next Steps

After presenting the report, offer these options:

```markdown
---

### Next Steps

I found N issues (P0: _, P1: _, P2: _, P3: _).

**How would you like to proceed?**

1. **Post as PR review** — I'll submit this as a `gh pr review` comment
2. **Deep dive** — Pick specific findings to investigate further
3. **Re-run a dimension** — Repeat one dimension in more depth
4. **Done** — Review complete, no further action needed
```

**Attribution**: When posting to GitHub (option 1), always append the following line at the very end of the comment body:

```
> Generated by `/code-review-expert` in forge
```

---

## Key Guidelines

- **Be precise**: Always include `file_path:line_number` references from the diff
- **Be actionable**: Every finding must include a concrete suggestion or fix
- **Be balanced**: Always include positive observations — what the PR does well
- **Focus on the diff**: Review what changed, not pre-existing issues in unchanged code
- **Don't nitpick formatting**: Trust `ruff` (via `make lint` / `make format`) for style enforcement
- **Apply project conventions**: Use AGENTS.md as the authoritative standard for this codebase
- **Severity discipline**: Reserve P0 for genuine security/correctness blockers; don't inflate severity
