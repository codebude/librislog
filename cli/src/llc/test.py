import subprocess
from pathlib import Path

import typer
from llc._interactive import console

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_BACKEND = _PROJECT_ROOT / "backend"
_CLI = _PROJECT_ROOT / "cli"
_FRONTEND = _PROJECT_ROOT / "frontend"


def cmd_backend() -> None:
    console.print("[bold]Running backend tests with coverage...[/bold]")
    code = subprocess.call(["uv", "run", "pytest"], cwd=str(_BACKEND))
    if code != 0:
        raise typer.Exit(code=code)


def cmd_cli() -> None:
    console.print("[bold]Running CLI tests...[/bold]")
    code = subprocess.call(["uv", "run", "pytest"], cwd=str(_CLI))
    if code != 0:
        raise typer.Exit(code=code)


def cmd_frontend() -> None:
    console.print("[bold]Running frontend tests with coverage...[/bold]")
    code = subprocess.call(["npm", "run", "test:coverage"], cwd=str(_FRONTEND))
    if code != 0:
        raise typer.Exit(code=code)


def cmd_e2e(*, grep: str | None = None) -> None:
    console.print("[bold]Running frontend E2E tests (Docker)...[/bold]")
    cmd = ["npm", "run", "test:e2e", "--"]
    if grep:
        cmd.extend(["--grep", grep])
    code = subprocess.call(cmd, cwd=str(_FRONTEND))
    if code != 0:
        raise typer.Exit(code=code)


def cmd_all() -> None:
    console.print("[bold]Running all test suites...[/bold]\n")

    suites = [
        ("Backend", ["uv", "run", "pytest"], _BACKEND),
        ("CLI", ["uv", "run", "pytest"], _CLI),
        ("Frontend", ["npm", "run", "test:coverage"], _FRONTEND),
        ("E2E", ["npm", "run", "test:e2e"], _FRONTEND),
    ]

    results: dict[str, int] = {}
    for name, cmd, cwd in suites:
        console.print(f"[bold]=== {name} ===[/bold]")
        try:
            r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
            results[name] = r.returncode
            print(r.stdout)
            if r.stderr:
                print(r.stderr)
        except Exception as exc:
            console.print(f"[red]{name}: failed to run — {exc}[/red]")
            results[name] = 1
        print()

    console.print("[bold]=== Summary ===[/bold]")
    any_failed = False
    for name, code in results.items():
        if code == 0:
            console.print(f"  [green]{name}: PASSED[/green]")
        else:
            console.print(f"  [red]{name}: FAILED (exit code {code})[/red]")
            any_failed = True

    if any_failed:
        raise typer.Exit(code=1)
