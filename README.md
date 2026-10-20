# SIH-CLI-MCP

Scrapes the [Smart India Hackathon 2026 problem statements](https://www.sih.gov.in/sih2026PS) and exposes them as a CLI (`sih`) and an MCP server (`sih-mcp`) so you or an agent can search, filter and sort them.

The site has no API. The table and each statement's details are server-rendered, so they are parsed from the HTML and cached for 6 hours.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/kry0sc0pic/SIH-CLI-MCP && cd SIH-CLI-MCP
uv sync
uv run sih refresh
```

Run commands with `uv run sih ...`, or `uv tool install .` to get a plain `sih` on your PATH.

## Concepts

- **Ranked search.** A query is scored with BM25 over title, theme/organization/department and description (title hits weigh most). It handles plurals (`drones`), prefixes (`agri`), typos (`satelite`) and related words (`farming` also finds agriculture, crop and farmer statements; the synonym list is in `src/sih/ranking.py`). Statements matching only some of your words still appear, ranked lower; very weak matches next to strong ones are dropped.
- **Closed statements.** Once idea submissions close, the site shows "Idea Submissions Closed" instead of a count. Those statements are **hidden by default**. With `--closed` (CLI) or `include_closed` (MCP) they are included, but always listed after open ones whatever the sort. Their idea count is `null`/`closed`, never `0`, so `--min-ideas`/`--max-ideas` exclude them.
- **Ideas.** Shown as `submitted/cap`, for example `3/500`.
- **Dates** are ISO `YYYY-MM-DD`. `--open` means the deadline has not passed (statements with no parseable deadline are kept).

## CLI

```
sih [COMMAND] [OPTIONS]
```

### `sih search [QUERY]`

Ranked search, filter and sort. Prints a table; `--json` prints machine-readable output including `total` and `closed_hidden`.

| Option | Description |
|---|---|
| `QUERY` | Free-text query, ranked by relevance. Optional. |
| `-o, --org TEXT` | Organization contains this text (case-insensitive). |
| `-c, --category TEXT` | Category, `software` or `hardware`. |
| `-t, --theme TEXT` | Theme contains this text, for example `agriculture`. |
| `--dept TEXT` | Department contains this text. |
| `--min-ideas N` / `--max-ideas N` | Bounds on ideas already submitted (low means less competition). |
| `--open` | Only statements whose deadline has not passed. |
| `--from DATE` / `--to DATE` | Inclusive deadline range, `YYYY-MM-DD`. |
| `-s, --sort KEY` | `relevance`, `ps_number`, `title`, `organization`, `category`, `theme`, `ideas`, `deadline`. Default: `relevance` with a query, otherwise `ps_number`. |
| `--desc` | Reverse the sort. |
| `-n, --limit N` | Page size (default 20). |
| `--offset N` | Skip the first N results. |
| `--closed` | Include statements whose submissions are closed (listed last). |
| `--json` | JSON output. |

```sh
sih search "drone surveillance"
sih search --category software --theme agriculture --sort ideas
sih search --open --from 2026-10-20 --to 2026-10-31 --json
sih search "flood" --closed --limit 50
```

### `sih show PS_NUMBER`

Full details for one statement: organization, department, category, theme, ideas, deadline, dataset/YouTube/contact links and the complete description. Accepts `SIH26265` or just `26265`, and finds closed statements too. `--json` for JSON.

### `sih facets`

Counts per category, theme and organization. Open statements only unless `--closed`.

### `sih refresh`

Re-download from sih.gov.in and rewrite the cache. Other commands refresh automatically when the cache is older than 6 hours.

### `sih install AGENT`

Register the MCP server with a coding agent. See [Adding to agents](#adding-to-agents).

### `sih mcp`

Run the MCP server over stdio (same as `sih-mcp`).

## MCP server

Tools:

| Tool | Arguments |
|---|---|
| `search_problem_statements` | `query`, `organization`, `category`, `theme`, `department`, `min_ideas`, `max_ideas`, `open_only`, `deadline_from`, `deadline_to`, `sort`, `desc`, `limit` (20), `offset`, `full_description`, `include_closed`. Same semantics as `sih search`. Descriptions are truncated to 240 characters unless `full_description` is true. The result has `total`, `returned`, `results` and, when closed statements are hidden, `closed_hidden`. |
| `get_problem_statement` | `ps_number` (`SIH26265` or `26265`). Returns the full record, or `{"error": ...}`. |
| `list_facets` | `include_closed`. Counts per organization, category and theme, plus `closed_hidden`. |
| `refresh_problem_statements` | None. Forces a re-download. |

Each statement has: `ps_number`, `ps_id`, `title`, `organization`, `department`, `category`, `theme`, `ideas` (null when closed), `ideas_cap`, `closed`, `deadline`, `description`, `youtube`, `dataset_links`, `contact`.

## Adding to agents

```sh
sih install AGENT            # print the command or config snippet
sih install AGENT --apply    # actually write it
```

`AGENT` is one of `claude`, `codex`, `gemini`, `cursor`, `opencode`, `claude-desktop`, `hermes`, or `all`.

| Option | Description |
|---|---|
| `--apply` | Perform the registration instead of printing it. |
| `--source local\|git` | `local` runs from this checkout (default when run from one); `git` runs from GitHub via `uvx`, no clone needed. |

How each agent is handled:

| Agent | What `--apply` does |
|---|---|
| `claude` | Runs `claude mcp add sih -- ...` |
| `codex` | Runs `codex mcp add sih -- ...` |
| `gemini` | Adds `sih` under `mcpServers` in `~/.gemini/settings.json` |
| `cursor` | Adds `sih` under `mcpServers` in `~/.cursor/mcp.json` |
| `opencode` | Adds `sih` under `mcp` in `~/.config/opencode/opencode.json` |
| `claude-desktop` | Adds `sih` under `mcpServers` in `~/Library/Application Support/Claude/claude_desktop_config.json` |
| `hermes` | Print-only (its config is YAML): prints a `mcp_servers:` block to paste into `~/.hermes/config.yaml` |

JSON configs are merged without touching your other servers, and files that aren't plain JSON (for example with comments) are left alone with an error.

Manual registration, for any MCP client:

```sh
claude mcp add sih -- uv run --directory /path/to/SIH-CLI-MCP sih-mcp
```

## Configuration

| Environment variable | Default | Purpose |
|---|---|---|
| `SIH_URL` | `https://www.sih.gov.in/sih2026PS` | Page to scrape. |
| `SIH_CACHE_DIR` | `~/.cache/sih` | Where `problem_statements.json` is cached (6 hour TTL). |

## Development

```sh
uv run pytest
```

Tests run against a small synthetic copy of the page and never touch the network or your real cache.

## License

GPL-3.0-or-later. See `LICENSE`.
