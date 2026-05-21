import typer
import llc._git
import llc._interactive
from llc._interactive import console


def cmd_sync() -> None:
    try:
        llc._git.fetch()
    except Exception:
        console.print("[red]Failed to fetch from origin.[/red]")
        raise typer.Exit(code=1)

    cur = llc._git.current_branch()
    console.print(f"Current branch: [bold]{cur}[/bold]")

    try:
        remotes = llc._git.remote_origin_branches()
    except Exception:
        console.print("[red]Failed to list remote branches.[/red]")
        raise typer.Exit(code=1)

    candidates = [b for b in remotes if b != cur]
    upstream = llc._git.get_upstream_branch()

    target = llc._interactive.select_from_list(
        candidates,
        title="Select origin branch to merge into current",
        preselect=upstream,
    )
    if target is None:
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit()

    try:
        console.print(f"Merging [bold]origin/{target}[/bold] into [bold]{cur}[/bold]...")
        llc._git.merge(target)
        llc._git.push()
        console.print(f"[green]Branch {cur} synced with origin/{target}![/green]")
    except Exception as exc:
        console.print(f"[red]Sync failed: {exc}[/red]")
        raise typer.Exit(code=1)
