from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claude_benchmark.tasks.schema import TaskDefinition


def create_workspace(
    task_dir: Path, profile_path: Path, task: TaskDefinition
) -> Path:
    workspace = Path(tempfile.mkdtemp(prefix=f"claude_benchmark_{task.name}_"))

    shutil.copy(profile_path, workspace / "CLAUDE.md")

    if task.starter_code:
        starter_path = task_dir / task.starter_code
        if starter_path.exists():
            shutil.copy(starter_path, workspace / starter_path.name)

    if task.starter_files:
        for file in task.starter_files:
            src = task_dir / file
            dst = workspace / file
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_file():
                shutil.copy(src, dst)
            elif src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)

    test_file_path = task_dir / task.scoring.test_file
    if test_file_path.exists():
        shutil.copy(test_file_path, workspace / test_file_path.name)

    if task.claudemd_rules:
        rules_path = task_dir / task.claudemd_rules
        if rules_path.exists():
            with open(rules_path) as f:
                rules_content = f.read()
            with open(workspace / "CLAUDE.md", "a") as f:
                f.write("\n\n")
                f.write(rules_content)

    if task.scoring.reference_solution:
        ref_path = task_dir / task.scoring.reference_solution
        if ref_path.exists():
            shutil.copy(ref_path, workspace / ref_path.name)

    return workspace


def capture_workspace_files(workspace: Path) -> dict[str, str]:
    files = {}
    for item in workspace.rglob("*"):
        if item.is_file():
            rel_path = item.relative_to(workspace)

            if rel_path.name == "CLAUDE.md":
                continue
            if ".claude" in rel_path.parts:
                continue

            with open(item) as f:
                files[str(rel_path)] = f.read()

    return files


def cleanup_workspace(workspace: Path) -> None:
    if workspace.exists():
        shutil.rmtree(workspace, ignore_errors=True)
