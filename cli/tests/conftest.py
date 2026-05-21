import subprocess
from collections.abc import Generator

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_subprocess(mocker) -> Generator:
    def _mock(stdout: str = "", stderr: str = "", returncode: int = 0):
        return mocker.patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=returncode,
                stdout=stdout, stderr=stderr,
            ),
        )
    return _mock
