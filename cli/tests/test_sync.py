from llc.main import app


class TestSync:
    def test_basic_sync(self, runner, mocker):
        mocker.patch("llc._git.fetch")
        mocker.patch("llc._git.current_branch", return_value="my-feature")
        mocker.patch("llc._git.remote_origin_branches", return_value=["main", "develop"])
        mocker.patch("llc._git.get_upstream_branch", return_value="develop")
        mocker.patch("llc._interactive.select_from_list", return_value="develop")
        mock_merge = mocker.patch("llc._git.merge")
        mock_push = mocker.patch("llc._git.push")

        result = runner.invoke(app, ["sync"])
        assert result.exit_code == 0
        mock_merge.assert_called_once_with("develop")
        mock_push.assert_called_once()

    def test_cancelled(self, runner, mocker):
        mocker.patch("llc._git.fetch")
        mocker.patch("llc._git.current_branch", return_value="my-feature")
        mocker.patch("llc._git.remote_origin_branches", return_value=["main", "develop"])
        mocker.patch("llc._interactive.select_from_list", return_value=None)

        result = runner.invoke(app, ["sync"])
        assert result.exit_code == 0
