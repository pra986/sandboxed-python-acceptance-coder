# Architecture: Sandboxed Python Acceptance Coder

## 1. Design Philosophy

Agentic coding assistants frequently suffer from two failure modes:
1. **Unverified execution claims**: The model outputs a fluent summary claiming the script works when it actually crashed, timed out, or failed edge-case assertions.
2. **Unbounded host execution**: Running LLM-generated Python directly in-process exposes the host filesystem and can hang indefinitely on infinite loops.

`sandboxed-python-acceptance-coder` enforces a strict separation between **candidate code**, **isolated execution**, **independent acceptance verification**, and **verbatim reporting**.

## 2. Core Components

- `sandbox_coder/models.py`: Pydantic v2 data contracts (`AcceptanceCase`, `CodingAssignment`, `SandboxExecutionResult`, `SolutionReport`).
- `sandbox_coder/engine.py`: `SandboxedAcceptanceCoder` orchestrating workspace confinement, subprocess execution with hard timeouts and POSIX resource limits, independent I/O acceptance checks, and `output/solution.md` report generation.
- `sandbox_coder/cli.py`: Command-line entrypoint (`sandbox-coder`) running built-in or JSON-defined assignments.
- `evaluation/eval_cases.json`: Deterministic evaluation suite covering valid execution, syntax/runtime errors, infinite-loop timeouts, and I/O acceptance assertions.

## 3. Execution & Safety Boundaries

### Workspace Confinement
- All generated code is written strictly inside `workspace_dir`.
- `entry_filename` is resolved and verified with `Path.resolve().is_relative_to(workspace_dir.resolve())`; any path traversal (e.g., `../escape.py` or absolute paths outside the workspace) raises a `ValueError`.

### Subprocess Isolation & Resource Bounds
- Code runs in a fresh `subprocess.run([sys.executable, str(script_path)], ...)` process with `cwd=workspace_dir`.
- Hard `timeout=assignment.timeout_seconds` kills infinite loops (`subprocess.TimeoutExpired`), returning `timed_out=True` and a non-zero `exit_code` (`-1` or `124`).
- On POSIX systems, `preexec_fn` applies `RLIMIT_CPU` and `RLIMIT_AS` (`memory_limit_mb`) to bound CPU time and virtual memory.

## 4. Independent I/O Acceptance & Verbatim Reporting

- Each `AcceptanceCase` is executed independently against the saved script with its own `stdin` and checked against `expected_exit_code`, `expected_stdout`, and `expected_substrings`.
- `output/solution.md` always embeds verbatim `exit_code`, `timed_out`, `stdout`, and `stderr`.
- **Fluent Summary Rejection**: If `execution.exit_code != 0` or `execution.timed_out` is `True`, any optimistic `proposed_summary` is rejected and replaced with an explicit failure summary referencing the non-zero exit code or timeout.
