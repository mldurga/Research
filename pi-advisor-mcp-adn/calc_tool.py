"""
Restricted Python calculation engine for the run_calculation MCP tool.

Purpose: let the Copilot agent perform real numerical work on PI data it has
already fetched (rolling averages, deviations from target, unit conversions,
cross-tag arithmetic, simple statistics) WITHOUT shipping raw arrays back and
forth through the LLM and without granting arbitrary code execution.

Security model (defence in depth, suitable for a POC with a small,
authenticated, allowlisted user population):

  1. AST validation BEFORE execution — the code is parsed and rejected if it
     contains: import statements, attribute/name access to double-underscore
     identifiers, or calls to disallowed builtins (open, eval, exec,
     __import__, compile, getattr, setattr, delattr, globals, locals, vars,
     input, breakpoint, exit, quit, help, memoryview, type).
  2. A minimal builtins whitelist — only pure computational builtins are
     exposed; there is no filesystem, network, process, or environment access
     in the execution namespace.
  3. Pre-imported, vetted libraries only: math, statistics, json, datetime,
     numpy (np), pandas (pd).
  4. Wall-clock timeout via a worker thread (CALC_TOOL_TIMEOUT, default 10 s).
  5. Output size cap (CALC_TOOL_MAX_OUTPUT chars).

This is NOT a sandbox against a determined attacker with code-authoring
access — it is a guardrail that makes the tool safe for its intended callers
(an LLM agent used by a small allowlisted group). For production, run the
whole server under a low-privilege account (recommended anyway) or disable
the tool with CALC_TOOL_ENABLED=false.
"""

from __future__ import annotations

import ast
import json
import logging
import math
import statistics
import threading
import datetime as _datetime
from typing import Any, Dict, Optional

from config import config

logger = logging.getLogger("pi_advisor.calc")

_BLOCKED_CALLS = {
    "eval", "exec", "compile", "open", "__import__", "input", "breakpoint",
    "getattr", "setattr", "delattr", "globals", "locals", "vars", "dir",
    "exit", "quit", "help", "memoryview", "type", "super", "object",
    "classmethod", "staticmethod", "property",
}

_SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
    "divmod": divmod, "enumerate": enumerate, "filter": filter, "float": float,
    "format": format, "frozenset": frozenset, "int": int, "isinstance": isinstance,
    "len": len, "list": list, "map": map, "max": max, "min": min, "pow": pow,
    "print": None,  # replaced per-run with a buffer-capturing print
    "range": range, "repr": repr, "reversed": reversed, "round": round,
    "set": set, "slice": slice, "sorted": sorted, "str": str, "sum": sum,
    "tuple": tuple, "zip": zip, "True": True, "False": False, "None": None,
    "ValueError": ValueError, "TypeError": TypeError, "KeyError": KeyError,
    "IndexError": IndexError, "ZeroDivisionError": ZeroDivisionError,
    "Exception": Exception,
}


class CalcValidationError(Exception):
    pass


def _validate_ast(code: str) -> ast.Module:
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise CalcValidationError(f"Syntax error: {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise CalcValidationError(
                "import statements are not allowed — numpy (np), pandas (pd), "
                "math, statistics, json and datetime are already available"
            )
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            raise CalcValidationError("global/nonlocal are not allowed")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise CalcValidationError(f"Access to dunder attribute '{node.attr}' is not allowed")
        if isinstance(node, ast.Name):
            if node.id.startswith("__"):
                raise CalcValidationError(f"Access to dunder name '{node.id}' is not allowed")
            if node.id in _BLOCKED_CALLS:
                raise CalcValidationError(f"'{node.id}' is not allowed in calculations")
    return tree


def _to_jsonable(value: Any) -> Any:
    """Convert numpy/pandas results into JSON-serialisable structures."""
    try:
        import numpy as np
        import pandas as pd
    except ImportError:  # pragma: no cover — deps always present in deployment
        np = pd = None  # type: ignore

    if pd is not None:
        if isinstance(value, pd.DataFrame):
            return json.loads(value.to_json(orient="split", date_format="iso"))
        if isinstance(value, pd.Series):
            return json.loads(value.to_json(orient="split", date_format="iso"))
        if isinstance(value, pd.Timestamp):
            return value.isoformat()
    if np is not None:
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
    if isinstance(value, (_datetime.datetime, _datetime.date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def _execute(code: str, data: Optional[Any]) -> Dict[str, Any]:
    """Run validated code in the restricted namespace (called in a worker thread)."""
    import numpy as np
    import pandas as pd

    tree = _validate_ast(code)

    printed: list[str] = []

    def _print(*args: Any, **kwargs: Any) -> None:
        printed.append(" ".join(str(a) for a in args))

    builtins_ns = dict(_SAFE_BUILTINS)
    builtins_ns["print"] = _print

    namespace: Dict[str, Any] = {
        "__builtins__": builtins_ns,
        "math": math,
        "statistics": statistics,
        "json": json,
        "datetime": _datetime,
        "np": np,
        "pd": pd,
        "data": data,
        "result": None,
    }

    # If the last top-level statement is a bare expression, capture its value
    # as the result (so one-liners work without assigning to `result`).
    capture_last = isinstance(tree.body[-1], ast.Expr) if tree.body else False
    if capture_last:
        last = tree.body.pop()
        assign = ast.Assign(
            targets=[ast.Name(id="_last_expr_value", ctx=ast.Store())],
            value=last.value,  # type: ignore[union-attr]
        )
        ast.copy_location(assign, last)
        ast.fix_missing_locations(assign)
        tree.body.append(assign)

    exec(compile(tree, "<calculation>", "exec"), namespace)  # noqa: S102 — AST-validated, restricted namespace

    result = namespace.get("result")
    if result is None and capture_last:
        result = namespace.get("_last_expr_value")

    return {
        "result": _to_jsonable(result),
        "printed": printed,
    }


def run_calculation_sync(code: str, data_json: str = "") -> Dict[str, Any]:
    """
    Validate and execute a calculation with timeout and output caps.
    Returns a JSON-safe dict; never raises.
    """
    if not config.calc.enabled:
        return {"error": "The calculation tool is disabled (CALC_TOOL_ENABLED=false)"}

    data: Optional[Any] = None
    if data_json:
        try:
            data = json.loads(data_json)
        except json.JSONDecodeError as exc:
            return {"error": f"data_json is not valid JSON: {exc}"}

    try:
        _validate_ast(code)  # fail fast before spawning the worker
    except CalcValidationError as exc:
        return {"error": str(exc)}

    # Run in a DAEMON thread so a runaway calculation can never block
    # process shutdown (non-daemon executor threads would hang service stop).
    box: Dict[str, Any] = {}

    def _worker() -> None:
        try:
            box["outcome"] = _execute(code, data)
        except CalcValidationError as exc:
            box["error"] = str(exc)
        except Exception as exc:  # noqa: BLE001 — reported to the caller
            box["error"] = f"Calculation raised {type(exc).__name__}: {exc}"

    thread = threading.Thread(target=_worker, daemon=True, name="calc-tool")
    thread.start()
    thread.join(timeout=config.calc.timeout_seconds)
    if thread.is_alive():
        return {"error": f"Calculation exceeded the {config.calc.timeout_seconds}s time limit"}
    if "error" in box:
        return {"error": box["error"]}
    outcome = box.get("outcome", {"result": None, "printed": []})

    text = json.dumps(outcome, default=repr)
    if len(text) > config.calc.max_output_chars:
        return {
            "error": (
                f"Result too large ({len(text)} chars > "
                f"{config.calc.max_output_chars}). Aggregate or slice the data "
                f"inside the calculation instead of returning raw arrays."
            )
        }
    return outcome
