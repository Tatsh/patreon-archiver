from __future__ import annotations

from typing import TYPE_CHECKING

from patreon_archiver.main import main

if TYPE_CHECKING:
    from click.testing import CliRunner
    from pytest_mock import MockerFixture


def test_main(runner: CliRunner, mocker: MockerFixture) -> None:
    """Test main function."""
    result = runner.invoke(main)
    assert result.exit_code == 0
