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
app.add_typer(pr_app)
app.add_typer(tag_app)


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


@app.command()
def sync():
    """Sync current branch with an origin branch."""
    from llc.sync import cmd_sync
    cmd_sync()
