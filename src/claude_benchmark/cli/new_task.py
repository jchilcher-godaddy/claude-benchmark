from pathlib import Path

import tomli_w
import typer


def new_task(
    name: str = typer.Argument(..., help="Task identifier e.g. 'my-code-gen-01'"),
    task_type: str = typer.Option("code-gen", "--task-type", "-t", help="Task type: code-gen, bug-fix, refactor, instruction"),
    difficulty: str = typer.Option("medium", "--difficulty", "-d", help="Difficulty: easy, medium, hard"),
    output_dir: Path = typer.Option(Path("tasks/custom"), "--output-dir", "-o", help="Parent directory for the new task"),
):
    """Create a new benchmark task from template."""
    dest = output_dir / name

    if dest.exists():
        typer.echo(f"Error: Task directory already exists: {dest}", err=True)
        raise typer.Exit(1)

    dest.mkdir(parents=True)

    task_data = {
        "name": name,
        "task_type": task_type,
        "difficulty": difficulty,
        "size": "function",
        "description": "TODO: Describe this benchmark task",
        "prompt": "TODO: Write the prompt Claude will receive.",
        "tags": [],
        "scoring": {
            "test_file": "test_solution.py"
        }
    }

    if task_type in ("bug-fix", "refactor"):
        task_data["starter_code"] = "starter.py"

    if task_type == "instruction":
        task_data["prompt_rules"] = ["TODO: Add rules"]

    toml_path = dest / "task.toml"
    with open(toml_path, "wb") as f:
        tomli_w.dump(task_data, f)

    test_path = dest / "test_solution.py"
    test_content = '"""Tests for the benchmark task solution.\n\nThese tests verify that Claude\'s output meets the task requirements.\nEdit this file to define your acceptance criteria.\n"""\nimport pytest\n\n\ndef test_solution_exists():\n    """Verify the solution file was created."""\n    # TODO: Update this to check for your expected output file\n    assert True, "Replace with actual solution verification"\n\n\ndef test_solution_correctness():\n    """Verify the solution produces correct results."""\n    # TODO: Import the solution and test its behavior\n    pytest.skip("TODO: Implement correctness tests")\n'
    test_path.write_text(test_content)

    if task_type in ("bug-fix", "refactor"):
        starter_path = dest / "starter.py"
        starter_path.write_text("# TODO: Add starter code here\n")

    typer.echo(f"Created task scaffold at {dest}/")
    typer.echo(f"  Edit {dest}/task.toml to define your task")
    typer.echo(f"  Edit {dest}/test_solution.py to add test cases")
