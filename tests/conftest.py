from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture
def examples() -> Path:
    return EXAMPLES
