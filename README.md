# SIH-CLI-MCP

Scrapes the [Smart India Hackathon 2026 problem statements](https://www.sih.gov.in/sih2026PS) and exposes them as a CLI (`sih`) and an MCP server (`sih-mcp`). The site has no API; the table and per-statement details are server-rendered, so they are parsed from the HTML and cached for 6 hours in `~/.cache/sih`.

## Setup

```sh
uv sync
uv run sih refresh
```

## CLI

```sh
uv run sih search "drone" --category software --sort ideas --max-ideas 5
uv run sih search --open --from 2026-10-20 --to 2026-10-31 --json
uv run sih show SIH26265
uv run sih facets
```

Interactive browser (list on the left, description and details on the right):

```sh
uv run sih browse                                   # same filters as search
uv run sih browse drone --category software --open --sort ideas
```

Keys: `↑/↓` move (running off the end of a page flips to the next one), `←/→` or `p`/`n` change page, `/` search, `s` cycle sort, `d` asc/desc, `o` open-only, `Tab` focus the details pane to scroll it, `q` quit. Closed statements show **closed** in red.

Filters: `--org --category --theme --dept --min-ideas --max-ideas --open --from --to`; sort with `--sort ps_number|title|organization|category|theme|ideas|deadline [--desc]`; page with `--limit --offset`.

## MCP

```sh
claude mcp add sih -- uv run --directory /path/to/SIH-CLI-MCP sih-mcp
```

Or let the CLI do it for any supported agent (`claude`, `codex`, `gemini`, `cursor`, `opencode`, `claude-desktop`, `hermes`, or `all`):

```sh
uv run sih install cursor                  # print the command/config snippet
uv run sih install cursor --apply          # actually write it
uv run sih install all --source git        # use uvx from GitHub instead of this checkout
```

`--apply` merges into existing JSON configs without touching other servers (it refuses files that aren't plain JSON), and shells out to `claude mcp add` / `codex mcp add`. Hermes uses YAML, so it prints a `mcp_servers:` block for `~/.hermes/config.yaml` to paste.

Tools: `search_problem_statements`, `get_problem_statement`, `list_facets`, `refresh_problem_statements`.

## Tests

```sh
uv run pytest
```

## License

GPL-3.0-or-later. See `LICENSE`.
