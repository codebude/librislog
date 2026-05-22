import subprocess
from pathlib import Path


class GitError(Exception):
    pass


def _ensure_git_repo() -> None:
    """Check CWD is inside a git repository or raise GitError."""
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            check=True,
            cwd=Path.cwd(),
        )
    except FileNotFoundError:
        raise GitError("git is not installed or not on PATH")
    except subprocess.CalledProcessError:
        raise GitError("Not inside a git repository")


def _run_git(args: list[str], *, interactive: bool = False) -> subprocess.CompletedProcess:
    if interactive:
        try:
            return subprocess.run(["git", *args], check=True)
        except FileNotFoundError:
            raise GitError("git is not installed or not on PATH")
        except subprocess.CalledProcessError as exc:
            raise GitError(str(exc))
    try:
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        raise GitError("git is not installed or not on PATH")
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr.strip() if exc.stderr else str(exc)
        raise GitError(msg)


def has_uncommitted_changes() -> bool:
    result = _run_git(["status", "--porcelain"])
    return bool(result.stdout.strip())


def current_branch() -> str:
    result = _run_git(["branch", "--show-current"])
    return result.stdout.strip()


def local_branches() -> list[str]:
    result = _run_git(["branch", "--format=%(refname:short)"])
    return [b.strip() for b in result.stdout.strip().splitlines() if b.strip()]


def remote_origin_branches() -> list[str]:
    result = _run_git(["branch", "-r", "--format=%(refname:short)"])
    branches = [b.strip() for b in result.stdout.strip().splitlines() if b.strip()]
    prefix = "origin/"
    return [b[len(prefix):] for b in branches if b.startswith(prefix) and b != "origin/HEAD"]


def fetch_tags(pattern: str = "v*") -> list[str]:
    result = _run_git(["tag", "-l", pattern, "--sort=-version:refname"])
    return [t.strip() for t in result.stdout.strip().splitlines() if t.strip()]


def checkout(branch: str) -> None:
    _run_git(["checkout", branch], interactive=True)


def pull(branch: str) -> None:
    _run_git(["pull", "origin", branch], interactive=True)


def tag(tagname: str) -> None:
    _run_git(["tag", tagname])


def push_tag(tagname: str) -> None:
    _run_git(["push", "origin", tagname], interactive=True)


def merge(remote_branch: str) -> None:
    _run_git(["merge", f"origin/{remote_branch}"], interactive=True)


def push() -> None:
    _run_git(["push"], interactive=True)


def fetch() -> None:
    _run_git(["fetch", "origin"])


def delete_tag(tagname: str) -> None:
    _run_git(["tag", "-d", tagname])


def delete_remote_tag(tagname: str) -> None:
    _run_git(["push", "origin", "--delete", tagname], interactive=True)


def tag_exists(tagname: str) -> bool:
    try:
        _run_git(["rev-parse", "-q", "--verify", f"refs/tags/{tagname}"])
        return True
    except GitError:
        return False


def get_upstream_branch() -> str | None:
    try:
        result = _run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"])
        upstream = result.stdout.strip()
        if upstream.startswith("origin/"):
            return upstream[len("origin/"):]
        return None
    except GitError:
        return None


def create_branch(branch_name: str, base_branch: str) -> None:
    _run_git(["branch", branch_name, base_branch])


def delete_branch(branch_name: str) -> None:
    _run_git(["branch", "-D", branch_name])


def push_and_set_upstream(branch_name: str) -> None:
    _run_git(["push", "--set-upstream", "origin", branch_name], interactive=True)
