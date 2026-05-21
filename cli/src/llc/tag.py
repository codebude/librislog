import re

import typer
import llc._git
import llc._interactive
from llc._interactive import console


def _parse_tag(tag: str) -> tuple[int, int, int, int | None]:
    m = re.match(r"^v(\d+)\.(\d+)\.(\d+)(?:-rc\.(\d+))?$", tag)
    if not m:
        raise ValueError(f"Invalid semver tag: {tag}")
    return (int(m[1]), int(m[2]), int(m[3]), int(m[4]) if m[4] else None)


def _compute_bump(version: tuple[int, int, int, int | None], bump_type: str) -> str:
    major, minor, patch, rc = version
    if bump_type == "major":
        return f"v{major + 1}.0.0"
    elif bump_type == "minor":
        return f"v{major}.{minor + 1}.0"
    else:
        return f"v{major}.{minor}.{patch + 1}"


def cmd_create() -> None:
    try:
        original_branch = llc._git.current_branch()
    except Exception:
        console.print("[red]Not inside a git repository.[/red]")
        raise typer.Exit(code=1)

    try:
        branches = llc._git.local_branches()
    except Exception:
        console.print("[red]Failed to list local branches.[/red]")
        raise typer.Exit(code=1)

    branch = llc._interactive.select_from_list(
        branches,
        title="Select branch to tag",
        preselect=original_branch,
    )
    if branch is None:
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit()

    try:
        tags = llc._git.fetch_tags("v*")
    except Exception:
        console.print("[red]Failed to fetch tags.[/red]")
        raise typer.Exit(code=1)

    version_tags = [t for t in tags if re.match(r"^v\d+\.\d+\.\d+(-rc\.\d+)?$", t)]

    if not version_tags:
        console.print("[yellow]No semantic version tags found on this branch.[/yellow]")
        new_version = llc._interactive.prompt_text("Enter version tag (e.g. v0.1.0)")
    else:
        latest = version_tags[0]
        parsed = _parse_tag(latest)
        console.print(f"Latest tag: [bold]{latest}[/bold]")

        major_v = _compute_bump(parsed, "major")
        minor_v = _compute_bump(parsed, "minor")
        patch_v = _compute_bump(parsed, "patch")

        bumps: dict[str, str] = {
            f"Major bump ({major_v})": major_v,
            f"Minor bump ({minor_v})": minor_v,
            f"Patch bump ({patch_v})": patch_v,
        }
        choices = list(bumps.keys()) + ["Enter custom"]
        choice = llc._interactive.select_from_list(choices, title="Select bump type")
        if choice is None:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit()

        if choice == "Enter custom":
            new_version = llc._interactive.prompt_text("Enter version tag")
        else:
            new_version = bumps[choice]

    if new_version is None or not new_version.strip():
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit()

    new_version = new_version.strip()

    if not re.match(r"^v\d+\.\d+\.\d+(-rc\.\d+)?$", new_version):
        console.print(f"[red]Invalid version format: {new_version}. Expected format like v1.2.3 or v1.2.3-rc.1[/red]")
        raise typer.Exit(code=1)

    if llc._git.tag_exists(new_version):
        console.print(f"[yellow]Tag {new_version} already exists.[/yellow]")
        if not llc._interactive.confirm(f"Overwrite tag [bold]{new_version}[/bold]?", default=False):
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit()

    if not llc._interactive.confirm(
        f"Create and push tag [bold]{new_version}[/bold] on [bold]{branch}[/bold]?",
        default=True,
    ):
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit()

    try:
        console.print(f"Checking out [bold]{branch}[/bold]...")
        llc._git.checkout(branch)
        console.print(f"Pulling latest [bold]{branch}[/bold]...")
        llc._git.pull(branch)
        console.print(f"Creating tag [bold]{new_version}[/bold]...")
        llc._git.tag(new_version)
        console.print(f"Pushing tag [bold]{new_version}[/bold]...")
        llc._git.push_tag(new_version)
        console.print(f"Restoring [bold]{original_branch}[/bold]...")
        llc._git.checkout(original_branch)
        console.print(f"[green]Tag {new_version} created and pushed![/green]")
    except Exception as exc:
        console.print(f"[red]Tag operation failed: {exc}[/red]")
        try:
            llc._git.checkout(original_branch)
        except Exception:
            pass
        raise typer.Exit(code=1)
