import questionary
from rich.console import Console

console = Console()


def confirm(prompt_text: str, *, default: bool = True) -> bool:
    result = questionary.confirm(prompt_text, default=default).ask()
    if result is None:
        return False
    return result


def prompt_text(prompt_text: str, *, default: str | None = None) -> str | None:
    return questionary.text(prompt_text, default=default or "").ask()


def select_from_list(
    items: list[str],
    *,
    title: str = "Select an option",
    preselect: str | None = None,
) -> str | None:
    if not items:
        console.print("[yellow]No items to select.[/yellow]")
        return None
    return questionary.select(title, choices=items, default=preselect).ask()
