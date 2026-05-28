import subprocess

import pytest

from llc._gh import GhError, check_gh, list_open_prs, create_pr, merge_pr


class TestCheckGh:
    def test_passes_when_authenticated(self, mocker):
        mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(args=[], returncode=0))
        check_gh()

    def test_raises_when_not_installed(self, mocker):
        mocker.patch("subprocess.run", side_effect=FileNotFoundError())
        with pytest.raises(GhError, match="not installed"):
            check_gh()

    def test_raises_when_not_authenticated(self, mocker):
        mocker.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, []))
        with pytest.raises(GhError, match="not authenticated"):
            check_gh()


class TestListOpenPRs:
    def test_parses_json_output(self, mock_subprocess):
        mock_subprocess(stdout='[{"number":1,"title":"Fix","headRefName":"f","baseRefName":"d","author":{"login":"user"}}]')
        prs = list_open_prs()
        assert len(prs) == 1
        assert prs[0]["number"] == 1

    def test_returns_empty_list(self, mock_subprocess):
        mock_subprocess(stdout="[]")
        assert list_open_prs() == []


class TestCreatePR:
    def test_calls_correct_command(self, mocker):
        mock = mocker.patch("subprocess.run")
        create_pr(base="main", head="feat/foo")
        cmd = mock.call_args[0][0]
        assert cmd[:5] == ["gh", "pr", "create", "--base", "main"]
        assert cmd[5:] == ["--head", "feat/foo", "--fill", "--assignee", "@me"]


class TestMergePR:
    def test_calls_correct_command(self, mocker):
        mock = mocker.patch("subprocess.run")
        merge_pr(42)
        cmd = mock.call_args[0][0]
        assert cmd == ["gh", "pr", "merge", "42", "-m"]
