# Developer CLI

LibrisLog includes a command-line tool for common development tasks. It automates pull requests, version tags, testing, and documentation.

## Installation

From the repository root:

```bash
cd cli
uv sync
```

Then run commands with:

```bash
uv run llc <command>
```

You can also install it in your environment:

```bash
uv pip install -e cli
```

## Usage

### `llc docs`

Build and preview the documentation site.

| Command | Description |
|---------|-------------|
| `llc docs build` | Build the VitePress site |
| `llc docs serve` | Start the VitePress dev server with hot-reload |
| `llc docs preview` | Preview the built site (run `build` first) |

### `llc test`

Run test suites with a single command.

| Command | Description |
|---------|-------------|
| `llc test backend` | Run backend pytest with coverage |
| `llc test cli` | Run CLI pytest |
| `llc test frontend` | Run frontend vitest with coverage |
| `llc test e2e` | Run frontend Playwright E2E tests (Docker) |
| `llc test all` | Run all four suites (backend, cli, frontend, e2e) |

### `llc pr`

Manage pull requests on GitHub.

| Command | Description |
|---------|-------------|
| `llc pr list` | List open pull requests |
| `llc pr create` | Interactive PR creation — selects head and base branches |
| `llc pr merge` | Interactive PR merge — select from open PRs |

### `llc tag`

Create and delete semantic version tags.

| Command | Description |
|---------|-------------|
| `llc tag create` | Interactive tag creation — picks the branch, suggests the next version (major/minor/patch bump), creates and pushes the tag |
| `llc tag delete` | Interactive tag deletion — select from recent tags or enter a name, deletes locally and remotely |

### `llc branch`

Create, delete, and sync local branches.

| Command | Description |
|---------|-------------|
| `llc branch create` | Interactive branch creation — enter a name, select a base, pushes to origin |
| `llc branch delete` | Interactive branch deletion — select a branch, auto-switches if currently on it |
| `llc branch sync` | Interactive sync — fetches origin, merges the selected remote branch into your current branch, pushes |
