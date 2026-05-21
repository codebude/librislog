import pytest
from llc.main import app


def _patch_pr(mocker, **kwargs):
    """Apply common patches for PR tests and return the create_pr mock."""
    mocker.patch("llc._gh.check_gh")
    for key, value in kwargs.items():
        mocker.patch(key, value)


class TestPRCreate:
    def test_without_changes(self, runner, mocker):
        _patch_pr(mocker)
        mocker.patch("llc._git.has_uncommitted_changes", return_value=False)
        mocker.patch("llc._git.remote_origin_branches", return_value=["main", "develop"])
        mocker.patch("llc._git.current_branch", return_value="my-feature")
        mocker.patch("llc._interactive.select_from_list", side_effect=["my-feature", "develop"])
        mock_create = mocker.patch("llc._gh.create_pr")

        result = runner.invoke(app, ["pr", "create"])
        assert result.exit_code == 0
        mock_create.assert_called_once_with(base="develop", head="my-feature")

    def test_with_uncommitted_changes_yes(self, runner, mocker):
        _patch_pr(mocker)
        mocker.patch("llc._git.current_branch")
        mocker.patch("llc._git.has_uncommitted_changes", return_value=True)
        mocker.patch("llc._interactive.confirm", return_value=True)

        result = runner.invoke(app, ["pr", "create"])
        assert result.exit_code == 0
        assert "commit" in result.stdout.lower()

    def test_with_uncommitted_changes_no(self, runner, mocker):
        _patch_pr(mocker)
        mocker.patch("llc._git.has_uncommitted_changes", return_value=True)
        mocker.patch("llc._interactive.confirm", return_value=False)
        mocker.patch("llc._git.remote_origin_branches", return_value=["main", "develop"])
        mocker.patch("llc._git.current_branch", return_value="my-feature")
        mocker.patch("llc._interactive.select_from_list", side_effect=["my-feature", "develop"])
        mock_create = mocker.patch("llc._gh.create_pr")

        result = runner.invoke(app, ["pr", "create"])
        assert result.exit_code == 0
        mock_create.assert_called_once()

    def test_preselects_main_when_head_is_develop(self, runner, mocker):
        _patch_pr(mocker)
        mocker.patch("llc._git.has_uncommitted_changes", return_value=False)
        mocker.patch("llc._git.remote_origin_branches", return_value=["main", "develop", "feature"])
        mocker.patch("llc._git.current_branch", return_value="develop")
        mocker.patch("llc._interactive.select_from_list", side_effect=["develop", "main"])
        mock_create = mocker.patch("llc._gh.create_pr")

        result = runner.invoke(app, ["pr", "create"])
        assert result.exit_code == 0
        mock_create.assert_called_once_with(base="main", head="develop")

    def test_not_in_git_repo(self, runner, mocker):
        mocker.patch("llc._git.current_branch", side_effect=Exception("Not a git repo"))

        result = runner.invoke(app, ["pr", "create"])
        assert result.exit_code == 1
        assert "git" in result.stdout.lower()

    def test_gh_not_installed(self, runner, mocker):
        mocker.patch("llc._git.current_branch")
        mocker.patch("llc._gh.check_gh", side_effect=Exception("gh is not installed"))

        result = runner.invoke(app, ["pr", "create"])
        assert result.exit_code == 1


class TestPRMerge:
    def test_no_open_prs(self, runner, mocker):
        _patch_pr(mocker)
        mocker.patch("llc._gh.list_open_prs", return_value=[])

        result = runner.invoke(app, ["pr", "merge"])
        assert result.exit_code == 0
        assert "No open" in result.stdout

    def test_selects_and_merges(self, runner, mocker):
        _patch_pr(mocker)
        mocker.patch(
            "llc._gh.list_open_prs",
            return_value=[
                {"number": 1, "title": "Fix bug", "headRefName": "fix", "baseRefName": "develop"},
            ],
        )
        mocker.patch("llc._interactive.select_from_list", return_value="#1 — Fix bug (fix → develop)")
        mock_merge = mocker.patch("llc._gh.merge_pr")

        result = runner.invoke(app, ["pr", "merge"])
        assert result.exit_code == 0
        mock_merge.assert_called_once_with(1)
