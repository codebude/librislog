import json
import subprocess


class GhError(Exception):
    pass


def _run_gh(args: list[str], *, interactive: bool = False) -> subprocess.CompletedProcess:
    if interactive:
        try:
            return subprocess.run(["gh", *args], check=True)
        except FileNotFoundError:
            raise GhError("GitHub CLI (gh) is not installed or not on PATH")
        except subprocess.CalledProcessError as exc:
            raise GhError(str(exc))
    try:
        return subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        raise GhError("GitHub CLI (gh) is not installed or not on PATH")
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr.strip() if exc.stderr else str(exc)
        raise GhError(msg)


def check_gh() -> None:
    try:
        subprocess.run(["gh", "auth", "status"], capture_output=True, check=True)
    except FileNotFoundError:
        raise GhError("GitHub CLI (gh) is not installed")
    except subprocess.CalledProcessError:
        raise GhError("GitHub CLI (gh) is not authenticated — run `gh auth login`")


def list_open_prs() -> list[dict]:
    result = _run_gh([
        "pr", "list", "--state", "open",
        "--json", "number,title,headRefName,baseRefName,author",
        "--limit", "100",
    ])
    return json.loads(result.stdout)


def create_pr(*, base: str, head: str) -> None:
    _run_gh([
        "pr", "create",
        "--base", base,
        "--head", head,
        "--fill",
        "--assignee", "@me",
    ], interactive=True)


def merge_pr(pr_number: int) -> None:
    _run_gh(["pr", "merge", str(pr_number), "-m"], interactive=True)
