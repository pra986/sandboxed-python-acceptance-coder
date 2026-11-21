# Sandboxed Python Acceptance Coder

**Project 37 / X6: Supplement / Agentic - CrewAI Sandbox Coder**

A CrewAI-inspired sandboxed Python coding agent engineered with strict subprocess execution timeouts, resource bounds, independent I/O acceptance tests, and verbatim exit-code reporting.

## Architecture

The system separates code generation from untrusted code execution and verification:

- **Workspace Isolation (`workspace_dir`)**: Generated scripts are constrained to a dedicated sandbox workspace directory; path traversal outside the workspace is rejected.
- **Subprocess Execution Sandbox**: Candidate Python code is executed in an isolated `subprocess.run` environment with `timeout` enforcement (killing infinite loops) and resource bounds (`RLIMIT_CPU`, `RLIMIT_AS` on POSIX).
- **Independent I/O Acceptance Engine**: Acceptance assertions evaluate actual `stdout`, `stderr`, `exit_code`, and generated artifacts against deterministic test cases independent of the LLM's self-reported claims.
- **Verbatim Reporting (`output/solution.md`)**: Every report embeds verbatim `exit_code`, `stdout`, and `stderr`. Fluent/optimistic summaries are rejected whenever `exit_code != 0`.

## 6-Stage Workflow

1. **Assignment Intake**: Parse `CodingAssignment` (prompt, entry script, timeout, resource limits, acceptance cases).
2. **Workspace Scoping**: Validate and resolve target script path inside the restricted `workspace_dir`.
3. **Code Materialization**: Write candidate Python implementation to the sandboxed script path.
4. **Bounded Subprocess Execution**: Run `python <script>` with hard timeout (`TimeoutExpired` handling) and resource limits, capturing `SandboxExecutionResult`.
5. **Independent I/O Acceptance**: Execute `eval_cases` / acceptance assertions against the actual process output and exit code.
6. **Verbatim Solution Report**: Emit `SolutionReport` and persist `output/solution.md`, enforcing the non-zero exit-code gate against fluent failure-masking summaries.

## Data Contract

- `CodingAssignment`: `task_id`, `description`, `code`, `entry_filename`, `timeout_seconds`, `memory_limit_mb`, `acceptance_cases`, `summary`
- `SandboxExecutionResult`: `exit_code`, `stdout`, `stderr`, `timed_out`, `duration_seconds`, `command`
- `SolutionReport`: `task_id`, `passed`, `execution`, `acceptance_passed`, `acceptance_details`, `summary`, `report_path`

## Production Controls

- **Hard Subprocess Timeouts**: Prevents infinite loops (`while True: pass`) from hanging the agent pipeline.
- **Workspace Write Guard**: Blocks `..` traversal or absolute paths escaping `workspace_dir`.
- **No Fluent Masking on Failure**: If `exit_code != 0` or `timed_out` is `True`, `SolutionReport` rejects optimistic summaries and surfaces verbatim `stderr` / `exit_code`.
- **Independent Acceptance Assertions**: Validates exact expected outputs, substrings, and exit codes rather than trusting LLM self-evaluation.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Run tests:

```bash
pytest -v
```

Run CLI demo:

```bash
python -m sandbox_coder.cli
```

## Attribution

Adapted and hardened from [ed-donner/agents](https://github.com/ed-donner/agents) (`3_crewai/reference/coder`).
 tests, and verbatim exit-code reporting.
