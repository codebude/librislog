import typer

app = typer.Typer(
    name="ll",
    help="LibrisLog developer CLI",
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
)

pr_app = typer.Typer(
    name="pr",
    help="Manage pull requests (create, merge, list)",
    rich_markup_mode="rich",
)
tag_app = typer.Typer(
    name="tag",
    help="Manage version tags",
    rich_markup_mode="rich",
)
test_app = typer.Typer(
    name="test",
    help="Run test suites",
    rich_markup_mode="rich",
)
branch_app = typer.Typer(
    name="branch",
    help="Manage branches (create, delete)",
    rich_markup_mode="rich",
)
app.add_typer(pr_app)
app.add_typer(tag_app)
app.add_typer(test_app)
app.add_typer(branch_app)


@pr_app.command("list")
def pr_list():
    """List open pull requests."""
    from llc.pr import cmd_list
    cmd_list()


@pr_app.command("create")
def pr_create():
    """Create a pull request with interactive branch selection."""
    from llc.pr import cmd_create
    cmd_create()


@pr_app.command("merge")
def pr_merge():
    """Merge an open pull request."""
    from llc.pr import cmd_merge
    cmd_merge()


@tag_app.command("create")
def tag_create():
    """Create and push a new version tag."""
    from llc.tag import cmd_create
    cmd_create()


@tag_app.command("delete")
def tag_delete():
    """Delete a tag locally and remotely."""
    from llc.tag import cmd_delete
    cmd_delete()


@test_app.command("backend")
def test_backend():
    """Run backend pytest with coverage."""
    from llc.test import cmd_backend
    cmd_backend()


@test_app.command("cli")
def test_cli():
    """Run CLI pytest."""
    from llc.test import cmd_cli
    cmd_cli()


@test_app.command("frontend")
def test_frontend():
    """Run frontend vitest with coverage."""
    from llc.test import cmd_frontend
    cmd_frontend()


@test_app.command("all")
def test_all():
    """Run all test suites and print coverage summary."""
    from llc.test import cmd_all
    cmd_all()


@branch_app.command("create")
def branch_create():
    """Create a new branch from a base branch."""
    from llc.branch import cmd_create
    cmd_create()


@branch_app.command("delete")
def branch_delete():
    """Delete a local branch."""
    from llc.branch import cmd_delete
    cmd_delete()


@app.command()
def sync():
    """Sync current branch with an origin branch."""
    from llc.sync import cmd_sync
    cmd_sync()
