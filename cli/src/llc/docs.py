import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console

console = Console()

DOCS_DIR = Path(__file__).resolve().parents[3] / "docs"


def _run_npm_script(script: str) -> None:
    if not (DOCS_DIR / "package.json").exists():
        console.print("[red]docs/package.json not found.")
        raise typer.Exit(1)
    if not (DOCS_DIR / "node_modules").exists():
        console.print("[yellow]node_modules not found. Running npm install...")
        try:
            subprocess.run(["npm", "install"], cwd=DOCS_DIR, check=True)
        except subprocess.CalledProcessError as exc:
            console.print(f"[red]npm install failed with exit code {exc.returncode}")
            raise typer.Exit(exc.returncode)
        except FileNotFoundError:
            console.print("[red]npm not found. Is Node.js installed?")
            raise typer.Exit(1)
    cmd = ["npm", "run", script]
    console.print(f"[dim]Running: {' '.join(cmd)} in {DOCS_DIR}")
    try:
        subprocess.run(cmd, cwd=DOCS_DIR, check=True)
    except subprocess.CalledProcessError as exc:
        console.print(f"[red]Command failed with exit code {exc.returncode}")
        raise typer.Exit(exc.returncode)
    except FileNotFoundError:
        console.print("[red]npm not found. Is Node.js installed?")
        raise typer.Exit(1)


def cmd_build() -> None:
    """Build the VitePress documentation site."""
    _run_npm_script("docs:build")
    dist = DOCS_DIR / ".vitepress" / "dist"
    console.print(f"[green]Docs built successfully: {dist}")


def cmd_serve() -> None:
    """Start the VitePress dev server for documentation."""
    _run_npm_script("docs:dev")


def cmd_preview() -> None:
    """Preview the built VitePress documentation site."""
    dist = DOCS_DIR / ".vitepress" / "dist"
    if not dist.exists():
        console.print("[yellow]No built documentation found. Run 'llc docs build' first.")
        raise typer.Exit(1)
    _run_npm_script("docs:preview")
