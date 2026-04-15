from pathlib import Path

import tomli_w
import typer


# Language-specific scaffolding templates
_SCAFFOLDING = {
    "python": {
        "test_file": "test_solution.py",
        "starter_file": "starter.py",
        "test_content": '"""Tests for the benchmark task solution.\n\nThese tests verify that Claude\'s output meets the task requirements.\nEdit this file to define your acceptance criteria.\n"""\nimport pytest\n\n\ndef test_solution_exists():\n    """Verify the solution file was created."""\n    # TODO: Update this to check for your expected output file\n    assert True, "Replace with actual solution verification"\n\n\ndef test_solution_correctness():\n    """Verify the solution produces correct results."""\n    # TODO: Import the solution and test its behavior\n    pytest.skip("TODO: Implement correctness tests")\n',
        "starter_content": "# TODO: Add starter code here\n",
        "extra_files": {},
    },
    "go": {
        "test_file": "solution_test.go",
        "starter_file": "starter.go",
        "test_content": 'package solution\n\nimport "testing"\n\nfunc TestSolutionExists(t *testing.T) {\n\t// TODO: Update this to verify your expected output\n\tt.Log("Replace with actual solution verification")\n}\n\nfunc TestSolutionCorrectness(t *testing.T) {\n\t// TODO: Import the solution and test its behavior\n\tt.Skip("TODO: Implement correctness tests")\n}\n',
        "starter_content": "package solution\n\n// TODO: Add starter code here\n",
        "extra_files": {
            "go.mod": "module solution\n\ngo 1.21\n",
        },
    },
    "javascript": {
        "test_file": "solution.test.js",
        "starter_file": "starter.js",
        "test_content": "const solution = require('./solution');\n\ntest('solution exists', () => {\n    // TODO: Update this to verify your expected output\n    expect(true).toBe(true);\n});\n\ntest('solution correctness', () => {\n    // TODO: Import the solution and test its behavior\n    expect(true).toBe(true);\n});\n",
        "starter_content": "// TODO: Add starter code here\n\nmodule.exports = {};\n",
        "extra_files": {},
    },
    "csharp": {
        "test_file": "SolutionTests.cs",
        "starter_file": "Starter.cs",
        "test_content": 'using Xunit;\n\npublic class SolutionTests\n{\n    [Fact]\n    public void SolutionExists()\n    {\n        // TODO: Update this to verify your expected output\n        Assert.True(true, "Replace with actual solution verification");\n    }\n\n    [Fact(Skip = "TODO: Implement correctness tests")]\n    public void SolutionCorrectness()\n    {\n        // TODO: Import the solution and test its behavior\n    }\n}\n',
        "starter_content": "// TODO: Add starter code here\n",
        "extra_files": {
            "Solution.csproj": '<Project Sdk="Microsoft.NET.Sdk">\n  <PropertyGroup>\n    <TargetFramework>net8.0</TargetFramework>\n    <ImplicitUsings>enable</ImplicitUsings>\n    <Nullable>enable</Nullable>\n    <IsPackable>false</IsPackable>\n  </PropertyGroup>\n  <ItemGroup>\n    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.8.0" />\n    <PackageReference Include="xunit" Version="2.6.2" />\n    <PackageReference Include="xunit.runner.visualstudio" Version="2.5.4" />\n  </ItemGroup>\n</Project>\n',
        },
    },
}


def _make_package_json(name: str) -> str:
    """Generate a package.json for JavaScript tasks."""
    import json

    return json.dumps(
        {
            "name": name,
            "version": "1.0.0",
            "private": True,
            "scripts": {"test": "jest"},
            "devDependencies": {"jest": "^29.0.0"},
        },
        indent=2,
    ) + "\n"


def new_task(
    name: str = typer.Argument(..., help="Task identifier e.g. 'my-code-gen-01'"),
    task_type: str = typer.Option("code-gen", "--task-type", "-t", help="Task type: code-gen, bug-fix, refactor, instruction"),
    difficulty: str = typer.Option("medium", "--difficulty", "-d", help="Difficulty: easy, medium, hard"),
    language: str = typer.Option("python", "--language", "-l", help="Language: python, go, javascript, csharp"),
    output_dir: Path = typer.Option(Path("tasks/custom"), "--output-dir", "-o", help="Parent directory for the new task"),
):
    """Create a new benchmark task from template."""
    if language not in _SCAFFOLDING:
        typer.echo(f"Error: Unsupported language '{language}'. Choose from: {', '.join(_SCAFFOLDING)}", err=True)
        raise typer.Exit(1)

    dest = output_dir / name

    if dest.exists():
        typer.echo(f"Error: Task directory already exists: {dest}", err=True)
        raise typer.Exit(1)

    dest.mkdir(parents=True)

    scaffold = _SCAFFOLDING[language]

    task_data = {
        "name": name,
        "task_type": task_type,
        "difficulty": difficulty,
        "size": "function",
        "description": "TODO: Describe this benchmark task",
        "prompt": "TODO: Write the prompt Claude will receive.",
        "tags": [],
        "scoring": {
            "test_file": scaffold["test_file"],
        },
    }

    if language != "python":
        task_data["language"] = language

    if task_type in ("bug-fix", "refactor"):
        task_data["starter_code"] = scaffold["starter_file"]

    if task_type == "instruction":
        task_data["prompt_rules"] = ["TODO: Add rules"]

    toml_path = dest / "task.toml"
    with open(toml_path, "wb") as f:
        tomli_w.dump(task_data, f)

    test_path = dest / scaffold["test_file"]
    test_path.write_text(scaffold["test_content"])

    if task_type in ("bug-fix", "refactor"):
        starter_path = dest / scaffold["starter_file"]
        starter_path.write_text(scaffold["starter_content"])

    # Write language-specific extra files
    for filename, content in scaffold["extra_files"].items():
        (dest / filename).write_text(content)

    # JavaScript gets a dynamic package.json
    if language == "javascript":
        (dest / "package.json").write_text(_make_package_json(name))

    typer.echo(f"Created {language} task scaffold at {dest}/")
    typer.echo(f"  Edit {dest}/task.toml to define your task")
    typer.echo(f"  Edit {dest}/{scaffold['test_file']} to add test cases")
