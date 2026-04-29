# Offline PNM Visits Report

Daily Slack report of "Surprise physical visit at CSP" form responses, posted at 10:00 AM IST.

## What it does

1. Pulls submissions from the [Google Form responses sheet](https://docs.google.com/spreadsheets/d/1wTCNVePUf3jIPYgWH6lRREZevaVuGCZnd578AJmlmIY/edit?gid=415112236) (published-to-web CSV).
2. Filters to four submitters: Fahad, Ajinkya, Anurag, Gaurav.
3. Classifies each visit by `Device LED Status`:
   - `All ON` / `Only Power Led glowing` → no issue
   - contains `Internet Led not glowing` → **Unknown Bug**
   - anything else → **CSP Issue**
4. Renders an HTML table, screenshots it via headless Chrome, and uploads the PNG to Slack with a tagged comment.
5. Cutoff: end of yesterday IST (today's submissions are excluded).

## Columns

| Name | # Visits | CSP Issue | Unknown Bug | D-1 | D-2 | D-3 | TTD |

- `# Visits` — count of yesterday's submissions
- `CSP Issue` — count + (% of yesterday's visits)
- `Unknown Bug` — count + (% of yesterday's visits) — `Net led is not glowing`
- `D-1 / D-2 / D-3` — visit counts on yesterday / 2 days back / 3 days back
- `TTD` — lifetime visits + (% that were CSP issues)

## Deploy

Set these GitHub Actions secrets in this repo:

| Secret | Value |
|---|---|
| `SLACK_BOT_TOKEN` | xoxb- bot token with `chat:write` and `files:write` scopes |
| `SLACK_CHANNEL_ID` | Target channel ID (e.g. `C0XXXXX`) |
| `HARMEET_USER_ID` | (optional) defaults to `U077923R68H` |
| `WHATSAPPER_USER_ID` | (optional) defaults to `U040Y7SEUSU` |

Workflow runs daily on cron `30 4 * * *` (UTC) and is manually triggerable via `gh workflow run "Daily PNM visits report"`.
