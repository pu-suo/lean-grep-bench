from typer.testing import CliRunner

from leangrep_bench import __version__
from leangrep_bench.cli import app


def test_version_constant() -> None:
    assert __version__ == "0.0.0"


def test_cli_version_command() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
