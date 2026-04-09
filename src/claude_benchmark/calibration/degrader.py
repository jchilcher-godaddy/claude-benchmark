"""Generate calibration samples at different quality tiers from reference solutions.

Tiers:
- gold: unchanged reference solution
- mild: docstrings stripped (tests readability sensitivity)
- broken: subtle logic error introduced (tests correctness detection)
- severe: docstrings stripped + variables renamed to single letters + type hints removed +
  try/except flattened
"""

from __future__ import annotations

import ast
import random
import re
from dataclasses import dataclass
from pathlib import Path

from claude_benchmark.tasks.loader import load_task


@dataclass
class CalibrationSample:
    task_name: str
    tier: str  # "gold", "mild", "severe"
    code: str
    task_description: str
    reference_solution: str


class _DocstringStripper(ast.NodeTransformer):
    """Remove docstrings from functions, classes, and the module."""

    def _strip_docstring(self, node: ast.AST) -> ast.AST:
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        ):
            node.body = node.body[1:] or [ast.Pass()]
        return node

    def visit_Module(self, node: ast.Module) -> ast.Module:
        self.generic_visit(node)
        return self._strip_docstring(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        self.generic_visit(node)
        return self._strip_docstring(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        self.generic_visit(node)
        return self._strip_docstring(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        self.generic_visit(node)
        return self._strip_docstring(node)


class _VariableRenamer(ast.NodeTransformer):
    """Rename local variables to single-letter names."""

    _LETTERS = "abcdefghijklmnopqrstuvwxyz"

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        self.generic_visit(node)
        return self._rename_locals(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        self.generic_visit(node)
        return self._rename_locals(node)

    def _rename_locals(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        # Collect parameter names (don't rename these)
        param_names = set()
        for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
            param_names.add(arg.arg)
        if node.args.vararg:
            param_names.add(node.args.vararg.arg)
        if node.args.kwarg:
            param_names.add(node.args.kwarg.arg)

        # Find local assignment targets
        local_names: list[str] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                if child.id not in param_names and child.id not in local_names:
                    local_names.append(child.id)

        # Build rename map
        rename_map: dict[str, str] = {}
        idx = 0
        for name in local_names:
            if idx < len(self._LETTERS):
                new_name = self._LETTERS[idx]
                # Avoid collisions with params
                while new_name in param_names or new_name in rename_map.values():
                    idx += 1
                    if idx >= len(self._LETTERS):
                        break
                    new_name = self._LETTERS[idx]
                if idx < len(self._LETTERS):
                    rename_map[name] = new_name
                    idx += 1

        if not rename_map:
            return node

        # Apply renames
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and child.id in rename_map:
                child.id = rename_map[child.id]

        return node


class _TypeHintRemover(ast.NodeTransformer):
    """Remove type annotations from function signatures and variable annotations."""

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        self.generic_visit(node)
        node.returns = None
        for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
            arg.annotation = None
        if node.args.vararg:
            node.args.vararg.annotation = None
        if node.args.kwarg:
            node.args.kwarg.annotation = None
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        self.generic_visit(node)
        node.returns = None
        for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
            arg.annotation = None
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AST:
        if node.value is not None:
            return ast.Assign(
                targets=[node.target],
                value=node.value,
                lineno=node.lineno,
                col_offset=node.col_offset,
            )
        # Annotation-only (no value) — remove entirely
        return None


class _TryExceptFlattener(ast.NodeTransformer):
    """Replace try/except blocks with just the try body."""

    def visit_Try(self, node: ast.Try) -> list[ast.stmt]:
        self.generic_visit(node)
        return node.body


class _LogicErrorIntroducer(ast.NodeTransformer):
    """Introduce a subtle logic error into the code.

    Applies ONE of these transformations (chosen randomly with seed):
    - Replace >= with > (off-by-one)
    - Replace +1 with +0 or -1
    - Replace True with False in a return statement
    - Swap two adjacent arguments in a function call
    """

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.mutation_applied = False
        self.mutation_type = self.rng.choice(["comparison", "arithmetic", "boolean", "arg_swap"])

    def visit_Compare(self, node: ast.Compare) -> ast.Compare:
        """Replace >= with > for off-by-one errors."""
        if self.mutation_applied or self.mutation_type != "comparison":
            return node

        for i, op in enumerate(node.ops):
            if isinstance(op, ast.GtE):
                node.ops[i] = ast.Gt()
                self.mutation_applied = True
                return node
            elif isinstance(op, ast.LtE):
                node.ops[i] = ast.Lt()
                self.mutation_applied = True
                return node

        return node

    def visit_BinOp(self, node: ast.BinOp) -> ast.BinOp:
        """Replace +1 with +0 or -1."""
        if self.mutation_applied or self.mutation_type != "arithmetic":
            return node

        if isinstance(node.op, ast.Add) and isinstance(node.right, ast.Constant):
            if node.right.value == 1:
                node.right.value = self.rng.choice([0, -1])
                self.mutation_applied = True
            elif node.right.value == 0:
                node.right.value = -1
                self.mutation_applied = True

        return node

    def visit_Return(self, node: ast.Return) -> ast.Return:
        """Replace True with False in return statements."""
        if self.mutation_applied or self.mutation_type != "boolean":
            return node

        if isinstance(node.value, ast.Constant) and node.value.value is True:
            node.value.value = False
            self.mutation_applied = True

        return node

    def visit_Call(self, node: ast.Call) -> ast.Call:
        """Swap two adjacent arguments in a function call."""
        if self.mutation_applied or self.mutation_type != "arg_swap":
            return node

        if len(node.args) >= 2:
            idx = self.rng.randint(0, len(node.args) - 2)
            node.args[idx], node.args[idx + 1] = node.args[idx + 1], node.args[idx]
            self.mutation_applied = True

        return node


def _strip_docstrings_ast(code: str) -> str:
    tree = ast.parse(code)
    tree = _DocstringStripper().visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def _degrade_severe_ast(code: str) -> str:
    tree = ast.parse(code)
    tree = _DocstringStripper().visit(tree)
    tree = _VariableRenamer().visit(tree)
    tree = _TypeHintRemover().visit(tree)
    tree = _TryExceptFlattener().visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def _strip_docstrings_regex(code: str) -> str:
    """Regex fallback for stripping docstrings."""
    # Remove triple-quoted strings at the start of functions/classes/modules
    code = re.sub(r'(^\s*)(\"\"\"[\s\S]*?\"\"\")', r'\1pass', code, flags=re.MULTILINE)
    code = re.sub(r"(^\s*)(\'\'\'[\s\S]*?\'\'\')", r'\1pass', code, flags=re.MULTILINE)
    return code


def _degrade_mild(code: str) -> str:
    try:
        return _strip_docstrings_ast(code)
    except SyntaxError:
        return _strip_docstrings_regex(code)


def _degrade_severe(code: str) -> str:
    try:
        return _degrade_severe_ast(code)
    except SyntaxError:
        return _strip_docstrings_regex(code)


def _degrade_broken(code: str, seed: int = 42) -> str:
    """Introduce a subtle logic error into the code.

    Uses a seeded random number generator to ensure reproducibility.
    """
    try:
        tree = ast.parse(code)
        tree = _LogicErrorIntroducer(seed=seed).visit(tree)
        ast.fix_missing_locations(tree)
        return ast.unparse(tree)
    except SyntaxError:
        return code


def generate_calibration_samples(task_dirs: list[Path]) -> list[CalibrationSample]:
    """Generate calibration samples from task reference solutions.

    For each task with a reference solution, produces 4 samples:
    gold (unchanged), mild (docstrings stripped), broken (subtle logic error),
    severe (fully degraded).
    """
    samples: list[CalibrationSample] = []

    for task_dir in task_dirs:
        try:
            task = load_task(task_dir)
        except Exception:
            continue

        if not task.scoring.reference_solution:
            continue

        ref_path = task_dir / task.scoring.reference_solution
        if not ref_path.exists():
            continue

        try:
            reference_code = ref_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        base = CalibrationSample(
            task_name=task.name,
            tier="gold",
            code=reference_code,
            task_description=task.description,
            reference_solution=reference_code,
        )
        samples.append(base)

        mild_code = _degrade_mild(reference_code)
        samples.append(CalibrationSample(
            task_name=task.name,
            tier="mild",
            code=mild_code,
            task_description=task.description,
            reference_solution=reference_code,
        ))

        seed = hash(task.name) % (2**31)
        broken_code = _degrade_broken(reference_code, seed=seed)
        samples.append(CalibrationSample(
            task_name=task.name,
            tier="broken",
            code=broken_code,
            task_description=task.description,
            reference_solution=reference_code,
        ))

        severe_code = _degrade_severe(reference_code)
        samples.append(CalibrationSample(
            task_name=task.name,
            tier="severe",
            code=severe_code,
            task_description=task.description,
            reference_solution=reference_code,
        ))

    return samples
