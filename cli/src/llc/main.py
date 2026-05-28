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
    help="Manage branches (create, delete, sync)",
    rich_markup_mode="rich",
)
docs_app = typer.Typer(
    name="docs",
    help="Build and serve documentation",
    rich_markup_mode="rich",
)
app.add_typer(pr_app)
app.add_typer(tag_app)
app.add_typer(test_app)
app.add_typer(branch_app)
app.add_typer(docs_app)


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


@test_app.command("e2e")
def test_e2e(
    grep: str | None = typer.Option(None, "--grep", "-g", help="Filter tests by name")
):
    """Run frontend E2E tests (Docker)."""
    from llc.test import cmd_e2e
    cmd_e2e(grep=grep)


@test_app.command("all")
def test_all():
    """Run all test suites (backend, cli, frontend, e2e) and print summary."""
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


@branch_app.command("sync")
def branch_sync():
    """Sync current branch with an origin branch."""
    from llc.sync import cmd_sync
    cmd_sync()


@docs_app.command("build")
def docs_build():
    """Build the VitePress documentation site."""
    from llc.docs import cmd_build
    cmd_build()


@docs_app.command("serve")
def docs_serve():
    """Start the VitePress documentation dev server."""
    from llc.docs import cmd_serve
    cmd_serve()


@docs_app.command("preview")
def docs_preview():
    """Preview the built VitePress documentation site."""
    from llc.docs import cmd_preview
    cmd_preview()
