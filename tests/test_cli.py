import tomllib
from pathlib import Path

from typer.testing import CliRunner

from claude_benchmark.cli.main import app

runner = CliRunner()


def test_new_task_creates_directory_and_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["new-task", "my-test-task"])

    assert result.exit_code == 0
    assert "Created task scaffold at" in result.stdout

    task_dir = tmp_path / "tasks" / "custom" / "my-test-task"
    assert task_dir.exists()
    assert (task_dir / "task.toml").exists()
    assert (task_dir / "test_solution.py").exists()


def test_new_task_bug_fix_creates_starter_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["new-task", "bug-fix-task", "--task-type", "bug-fix"])

    assert result.exit_code == 0

    task_dir = tmp_path / "tasks" / "custom" / "bug-fix-task"
    assert (task_dir / "starter.py").exists()


def test_new_task_refuses_to_overwrite(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    task_dir = tmp_path / "tasks" / "custom" / "existing-task"
    task_dir.mkdir(parents=True)

    result = runner.invoke(app, ["new-task", "existing-task"])

    assert result.exit_code == 1
    assert "already exists" in result.output


def test_generated_task_toml_is_valid(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["new-task", "valid-task"])

    assert result.exit_code == 0

    toml_path = tmp_path / "tasks" / "custom" / "valid-task" / "task.toml"
    with open(toml_path, "rb") as f:
        data = tomllib.load(f)

    assert data["name"] == "valid-task"
    assert data["task_type"] == "code-gen"
    assert data["difficulty"] == "medium"
    assert "scoring" in data


def test_new_task_help_shows_help_text():
    result = runner.invoke(app, ["new-task", "--help"])

    assert result.exit_code == 0
    assert "Task identifier" in result.stdout
