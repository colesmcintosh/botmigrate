from pathlib import Path

import pytest
from typer.testing import CliRunner

from botmigrate.cli import app

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"

runner = CliRunner()


def cli(*args: object):
    """Run the botmigrate CLI in-process."""
    return runner.invoke(app, [str(a) for a in args])


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture
def examples() -> Path:
    return EXAMPLES
