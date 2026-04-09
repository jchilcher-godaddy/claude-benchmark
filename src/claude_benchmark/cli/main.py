import typer
from claude_benchmark import __version__
from claude_benchmark.cli.commands.calibrate import calibrate
from claude_benchmark.cli.commands.catalog_cmd import catalog_app
from claude_benchmark.cli.commands.compare import compare
from claude_benchmark.cli.commands.experiment import experiment
from claude_benchmark.cli.commands.export import export_data
from claude_benchmark.cli.commands.intake import intake
from claude_benchmark.cli.commands.report import report
from claude_benchmark.cli.commands.rescore import rescore
from claude_benchmark.cli.commands.run import run
from claude_benchmark.cli.new_task import new_task
from claude_benchmark.cli.profiles import list_profiles


app = typer.Typer(name="claude-benchmark", help="Benchmark tool for CLAUDE.md configurations")
app.command()(new_task)
app.command("profiles")(list_profiles)
app.command()(run)
app.command()(experiment)
app.command()(calibrate)
app.command()(report)
app.command("export")(export_data)
app.command()(rescore)
app.command()(intake)
app.command()(compare)
app.add_typer(catalog_app)


def version_callback(value: bool):
    if value:
        typer.echo(f"claude-benchmark version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    pass
