"""Tests for the reproducibility module: hashing, seeds, environment."""

from __future__ import annotations

from pathlib import Path

import pytest

from claude_benchmark.reproducibility.environment import capture_environment
from claude_benchmark.reproducibility.hashing import (
    hash_judge_prompt,
    hash_string,
    hash_task_set,
)
from claude_benchmark.reproducibility.seeds import (
    DEFAULT_BASE_SEED,
    generate_run_seed,
    set_global_seeds,
)


# ---------- helpers ----------------------------------------------------------


def _make_task(root: Path, name: str, *, prompt: str = "do x", reference: str = "x = 1") -> Path:
    """Create a minimal task directory for hashing tests."""
    task_dir = root / name
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.toml").write_text(f'name = "{name}"\nprompt = "{prompt}"\n', encoding="utf-8")
    (task_dir / "reference.py").write_text(reference, encoding="utf-8")
    (task_dir / "test_solution.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    return task_dir


# ---------- hash_string ------------------------------------------------------


def test_hash_string_is_sha256() -> None:
    # SHA-256 of "" is a well-known constant.
    assert hash_string("") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    # Determinism.
    assert hash_string("hello") == hash_string("hello")
    assert hash_string("hello") != hash_string("Hello")


# ---------- hash_task_set ----------------------------------------------------


def test_hash_task_set_stable_across_calls(tmp_path: Path) -> None:
    _make_task(tmp_path, "task-a")
    _make_task(tmp_path, "task-b")
    first = hash_task_set(tmp_path)
    second = hash_task_set(tmp_path)
    assert first == second
    assert first["task_count"] == 2
    assert set(first["task_hashes"]) == {"task-a", "task-b"}


def test_hash_task_set_changes_when_file_modified(tmp_path: Path) -> None:
    _make_task(tmp_path, "task-a")
    before = hash_task_set(tmp_path)["task_set_hash"]
    # Modify reference.py.
    (tmp_path / "task-a" / "reference.py").write_text("x = 2", encoding="utf-8")
    after = hash_task_set(tmp_path)["task_set_hash"]
    assert before != after


def test_hash_task_set_changes_when_file_added(tmp_path: Path) -> None:
    _make_task(tmp_path, "task-a")
    before = hash_task_set(tmp_path)["task_set_hash"]
    (tmp_path / "task-a" / "extra.txt").write_text("hello", encoding="utf-8")
    after = hash_task_set(tmp_path)["task_set_hash"]
    assert before != after


def test_hash_task_set_ignores_pycache(tmp_path: Path) -> None:
    _make_task(tmp_path, "task-a")
    before = hash_task_set(tmp_path)["task_set_hash"]
    cache = tmp_path / "task-a" / "__pycache__"
    cache.mkdir()
    (cache / "reference.cpython-311.pyc").write_bytes(b"\x00\x01\x02")
    after = hash_task_set(tmp_path)["task_set_hash"]
    assert before == after, "pycache files must not affect the hash"


def test_hash_task_set_missing_root_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        hash_task_set(tmp_path / "does-not-exist")


def test_hash_task_set_empty_dir_returns_zero_count(tmp_path: Path) -> None:
    result = hash_task_set(tmp_path)
    assert result["task_count"] == 0
    assert result["task_hashes"] == {}


# ---------- hash_judge_prompt ------------------------------------------------


def test_hash_judge_prompt_returns_expected_keys() -> None:
    out = hash_judge_prompt()
    for key in (
        "system_prompt_sha256",
        "criteria_sha256",
        "schema_sha256",
        "judge_module_sha256",
        "judge_model_alias",
    ):
        assert key in out, f"missing key {key}"
    # All sha256 fields are 64 hex chars.
    for key in (
        "system_prompt_sha256",
        "criteria_sha256",
        "schema_sha256",
    ):
        assert len(out[key]) == 64
        int(out[key], 16)  # parses as hex


def test_hash_judge_prompt_is_stable() -> None:
    assert hash_judge_prompt() == hash_judge_prompt()


# ---------- seeds ------------------------------------------------------------


def test_generate_run_seed_deterministic() -> None:
    a = generate_run_seed("exp-1", "haiku/empty/task-a/run-1")
    b = generate_run_seed("exp-1", "haiku/empty/task-a/run-1")
    assert a == b


def test_generate_run_seed_differs_for_different_run_keys() -> None:
    a = generate_run_seed("exp-1", "haiku/empty/task-a/run-1")
    b = generate_run_seed("exp-1", "haiku/empty/task-a/run-2")
    assert a != b


def test_generate_run_seed_differs_for_different_experiments() -> None:
    a = generate_run_seed("exp-1", "haiku/empty/task-a/run-1")
    b = generate_run_seed("exp-2", "haiku/empty/task-a/run-1")
    assert a != b


def test_generate_run_seed_changes_with_base_seed() -> None:
    a = generate_run_seed("exp-1", "k", base_seed=DEFAULT_BASE_SEED)
    b = generate_run_seed("exp-1", "k", base_seed=DEFAULT_BASE_SEED + 1)
    assert a != b


def test_generate_run_seed_in_uint64_range() -> None:
    seed = generate_run_seed("exp-1", "k")
    assert 0 <= seed < 2**64


def test_set_global_seeds_seeds_random() -> None:
    import random

    set_global_seeds(123)
    a = random.random()
    set_global_seeds(123)
    b = random.random()
    assert a == b


def test_set_global_seeds_does_not_crash_without_numpy() -> None:
    # Whether numpy is installed or not, this must not raise.
    set_global_seeds(42)


# ---------- environment ------------------------------------------------------


def test_capture_environment_returns_expected_keys() -> None:
    env = capture_environment()
    expected = {
        "python_version",
        "python_implementation",
        "platform",
        "cb_version",
        "pip_freeze",
        "git_commit",
        "git_dirty",
        "git_branch",
    }
    assert expected.issubset(env.keys())


def test_capture_environment_pip_freeze_is_sorted_list() -> None:
    env = capture_environment()
    pip = env["pip_freeze"]
    assert isinstance(pip, list)
    if pip:
        # All entries are "name==version" strings.
        for item in pip:
            assert "==" in item
        # Lowercase-sorted.
        assert pip == sorted(pip, key=str.lower)


def test_capture_environment_does_not_raise_on_clean_repo() -> None:
    # Smoke test: the function runs to completion in this test env.
    env = capture_environment()
    assert isinstance(env["git_dirty"], bool)
