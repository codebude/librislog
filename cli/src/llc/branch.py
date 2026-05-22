import typer
import llc._git
import llc._interactive
from llc._interactive import console
from llc._git import GitError


def cmd_delete() -> None:
    """Delete a local branch."""
    try:
        llc._git._ensure_git_repo()

        branches = llc._git.local_branches()
        if not branches:
            console.print("[yellow]No local branches found.[/yellow]")
            raise typer.Exit()

        selected = llc._interactive.select_from_list(
            branches, title="Select a branch to delete"
        )
        if selected is None:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit()

        current = llc._git.current_branch()
        switch_to: str | None = None

        if selected == current:
            others = [b for b in branches if b != current]
            if not others:
                console.print("[red]Cannot delete the only branch.[/red]")
                raise typer.Exit(code=1)
            switch_to = llc._interactive.select_from_list(
                others, title="Select a branch to switch to before deletion"
            )
            if switch_to is None:
                console.print("[yellow]Cancelled.[/yellow]")
                raise typer.Exit()

        confirmed = llc._interactive.confirm(
            f"Are you sure you want to delete branch [bold]{selected}[/bold]?",
            default=False,
        )
        if not confirmed:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit()

        if switch_to:
            console.print(f"Switching to [green]{switch_to}[/green]...")
            llc._git.checkout(switch_to)

        console.print(f"Deleting branch [red]{selected}[/red]...")
        llc._git.delete_branch(selected)
        console.print(f"[green]✓[/green] Branch [bold]{selected}[/bold] deleted.")

    except GitError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)


def cmd_create() -> None:
    """Create a new branch from a base branch."""
    try:
        llc._git._ensure_git_repo()

        name = llc._interactive.prompt_text("Branch name")
        if not name:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit()

        branches = llc._git.local_branches()
        if not branches:
            console.print("[red]No local branches available as base.[/red]")
            raise typer.Exit(code=1)

        preselect = "develop" if "develop" in branches else None
        base = llc._interactive.select_from_list(
            branches, title="Select base branch", preselect=preselect
        )
        if base is None:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit()

        console.print(f"Creating branch [green]{name}[/green] from [blue]{base}[/blue]...")
        llc._git.create_branch(name, base)

        console.print("Setting upstream and pushing to origin...")
        llc._git.push_and_set_upstream(name)

        console.print(f"Checking out [green]{name}[/green]...")
        llc._git.checkout(name)
        console.print(f"[green]✓[/green] Switched to new branch [bold]{name}[/bold].")

    except GitError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)
