"""Safe Python transform engine for data import field transformations.

Uses RestrictedPython to compile user-provided Python code blocks into
restricted callables that run in a sandboxed environment.
"""

import ast
import textwrap
from typing import Any, Callable

from RestrictedPython import compile_restricted
from RestrictedPython.Eval import default_guarded_getitem
from RestrictedPython.Guards import safe_builtins, safer_getattr


class TransformExecutionError(Exception):
    """Raised when a compiled transform fails at runtime."""

# Whitelisted modules available in transform globals
_TRANSFORM_MODULES: dict[str, Any] = {
    "datetime": __import__("datetime"),
    "time": __import__("time"),
    "re": __import__("re"),
    "json": __import__("json"),
    "math": __import__("math"),
    "_strptime": __import__("_strptime"),
}

def _guarded_import(name: str, *args: Any, **kwargs: Any) -> Any:
    """Allow imports only for whitelisted modules and their submodules."""
    top = name.split(".")[0]
    if top in _ALLOWED_IMPORTS or top == "_strptime":
        return __import__(name, *args, **kwargs)
    raise ImportError(f"Import of '{name}' is not allowed in transforms")


# Build custom builtins that include safe_builtins plus our guarded __import__
_CUSTOM_BUILTINS: dict[str, Any] = dict(safe_builtins)
_CUSTOM_BUILTINS["__import__"] = _guarded_import


# Safe builtins + whitelisted names
_TRANSFORM_GLOBALS: dict[str, Any] = {
    "__builtins__": _CUSTOM_BUILTINS,
    "_getattr_": safer_getattr,
    "_getitem_": default_guarded_getitem,
    "_getiter_": iter,
    "_iter_unpack_sequence_": lambda x, y: x,
    **_TRANSFORM_MODULES,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "len": len,
    "range": range,
    "abs": abs,
    "min": min,
    "max": max,
    "sum": sum,
    "round": round,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "sorted": sorted,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "type": type,
    "isinstance": isinstance,
    "hasattr": hasattr,
    "getattr": safer_getattr,
}

# Whitelisted modules that may be imported
_ALLOWED_IMPORTS: set[str] = {"datetime", "time", "re", "json", "math"}

# AST node types that are forbidden in transforms
_FORBIDDEN_AST_NODES: tuple[type[ast.AST], ...] = (
    ast.Delete,
    ast.AugAssign,
    ast.AsyncFor,
    ast.AsyncWith,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.FunctionDef,
    ast.Lambda,
    ast.Yield,
    ast.YieldFrom,
    ast.Await,
    ast.Global,
    ast.Nonlocal,
    ast.Raise,
    ast.Assert,
    ast.With,
    ast.Try,
    ast.TryStar,
    ast.ExceptHandler,
)

# Forbidden function names (simple Name checks)
_FORBIDDEN_NAMES: set[str] = {"open", "__import__", "eval", "exec", "compile"}


def _validate_ast(source: str) -> list[str]:
    """Walk the AST and return a list of forbidden construct errors."""
    errors: list[str] = []
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        return [f"Syntax error: {exc}"]

    for node in ast.walk(tree):
        if isinstance(node, _FORBIDDEN_AST_NODES):
            errors.append(f"Forbidden construct: {node.__class__.__name__}")

        # Block calls to forbidden names like open(), eval(), etc.
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            errors.append(f"Forbidden name: {node.id}")

        # Allow imports only for whitelisted modules
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_module = alias.name.split(".")[0]
                if top_module not in _ALLOWED_IMPORTS:
                    errors.append(f"Forbidden import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            top_module = node.module.split(".")[0] if node.module else ""
            if top_module not in _ALLOWED_IMPORTS:
                errors.append(f"Forbidden import: {node.module}")

    return errors


def compile_transform(code: str) -> Callable[..., str]:
    """Compile a Python code block into a restricted callable.

    The user's code is wrapped in a function definition:

        def _transform(value, row, context):
            <user_code>

    Returns a callable that accepts ``(value, row, context)``.
    """
    # Strip leading/trailing whitespace but preserve internal indentation
    code = code.strip()
    if not code:
        raise ValueError("Transform code is empty")

    # AST validation before compilation
    ast_errors = _validate_ast(code)
    if ast_errors:
        raise ValueError("; ".join(ast_errors))

    # Detect single expression vs statement block.
    # If the code is a single expression, prepend "return" so the
    # function yields a value.  Otherwise leave it as-is (user may
    # already have return statements).
    try:
        ast.parse(code, mode="eval")
        body = f"    return {code}\n"
    except SyntaxError:
        body = textwrap.indent(code, "    ") + "\n"

    # Wrap user code in a function so multiline statements work.
    # Note: RestrictedPython forbids names starting with "_", so we use "transform".
    wrapped = textwrap.dedent(
        f"""\
def transform(value, row, context):
{body}"""
    )

    # Compile with RestrictedPython
    bytecode = compile_restricted(
        wrapped,
        filename="<transform>",
        mode="exec",
    )
    if bytecode is None:
        raise ValueError("RestrictedPython rejected the code")

    # Execute in restricted globals to define the function
    exec_globals = dict(_TRANSFORM_GLOBALS)
    exec(bytecode, exec_globals)

    fn = exec_globals.get("transform")
    if fn is None:
        raise ValueError("Failed to define transform function")

    return fn


def execute_transform(
    fn: Callable[..., Any],
    value: str,
    row: dict[str, str],
    context: dict[str, Any],
) -> str:
    """Execute a compiled transform and enforce string return."""
    try:
        result = fn(value=value, row=row, context=context)
    except Exception as exc:
        raise TransformExecutionError(str(exc)) from exc
    if result is None:
        return ""
    if not isinstance(result, str):
        return str(result)
    return result


def validate_transform(code: str) -> list[str]:
    """Validate transform code without compiling it.

    Returns a list of error messages (empty if valid).
    """
    code = code.strip()
    if not code:
        return ["Transform code is empty"]

    errors = _validate_ast(code)
    if errors:
        return errors

    # Try compiling to catch RestrictedPython-level rejections
    wrapped = textwrap.dedent(
        f"""\
def transform(value, row, context):
{textwrap.indent(code, '    ')}
"""
    )

    try:
        bytecode = compile_restricted(
            wrapped,
            filename="<transform>",
            mode="exec",
        )
        if bytecode is None:
            errors.append("RestrictedPython rejected the code")
    except Exception as exc:
        errors.append(f"Compilation error: {exc}")

    return errors
