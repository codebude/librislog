from llc.main import app


class TestHelp:
    def test_help_returns_zero(self, runner):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "LibrisLog" in result.stdout

    def test_pr_help(self, runner):
        result = runner.invoke(app, ["pr", "--help"])
        assert result.exit_code == 0
        assert "create" in result.stdout

    def test_tag_help(self, runner):
        result = runner.invoke(app, ["tag", "--help"])
        assert result.exit_code == 0
        assert "create" in result.stdout

    def test_sync_help(self, runner):
        result = runner.invoke(app, ["branch", "sync", "--help"])
        assert result.exit_code == 0
        assert "Sync" in result.stdout
