# Flamingo Watch bot — setup & troubleshooting

Status: **Phase 1** (Flamingo Watch → Discord, images only, no voting yet). See the owner's
`CLAUDE.md` for the full phase plan; `docs/bot-discovery.md` for how the feed/font/font decisions
below were reached.

## What this does

Every 30 minutes, a GitHub Actions job:
1. Fetches `https://flamingo-watch.com/data/articles-{CARD_LANG}.json` (the live site's own
   export — nothing scraped, no auth needed).
2. Renders any new story as a 1080×1350 JPEG card (Pillow, brand assets in `bot/assets` and
   `bot/fonts`).
3. Posts it to a private Discord channel via a webhook.
4. Records which stories it has already posted in `state.json`, committed to the orphan
   `bot-state` branch (never `main`) so the next run doesn't repost them.

Nothing runs on your PC. If your PC (which runs the site's own fetcher/publisher) is off, the
site just has no new stories, and the bot simply posts nothing that run — that's expected.

## Manual setup checklist (you, not Claude)

1. **Discord webhook:**
   - Create a private channel in your server for cards.
   - Channel settings → Integrations → Webhooks → New Webhook → copy the URL.
2. **GitHub secrets & variables** (repo → Settings → Secrets and variables → Actions):
   - Secret `DISCORD_WEBHOOK_URL` — the webhook URL from step 1. **Never paste this anywhere
     else** (not in chat, not in a commit, not in an issue).
   - Optional secret `ALERT_WEBHOOK_URL` — a second webhook (can be the same channel or a
     separate "bot alerts" channel) that gets a message if a run fails entirely.
   - Optional variables (all have working defaults, only set if you want something different):
     `CARD_LANG` (default `sq`), `HASHTAGS` (default `#Albania #FlamingoRevolution`),
     `MAX_PER_RUN` (default `5`), `FIRST_RUN_POST` (default `3`), `FEED_URL` (comma-separated
     override list, only needed if the default JSON endpoint ever goes down).
3. **Workflow permissions:** Settings → Actions → General → Workflow permissions → **Read and
   write permissions** (the job needs to push `state.json` to the `bot-state` branch).
4. **First run:** Actions tab → `ig-cards` workflow → **Run workflow**. Tick "Dry run" the first
   time if you just want to see it work without posting; leave it unticked to actually post 3
   cards to your Discord channel (first-run behavior — see below).

## Running locally (no GitHub needed)

```powershell
cd flamingo-watch_bot
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\cards_to_discord.py --dry-run
```

This fetches the real live feed (plain HTTPS, no secrets needed) and writes rendered cards to
`out\*.jpg` instead of posting them — open the files directly to check the design. It also writes
a local `state.json` (gitignored) so repeated dry-runs behave like repeated real runs (second
dry-run won't re-"post" the same stories).

To actually post from your machine (not recommended for routine use — GitHub Actions is the
intended runner), set `$env:DISCORD_WEBHOOK_URL` first and drop `--dry-run`.

## Configuration reference (Phase 1)

| Variable | Kind | Default | Purpose |
|---|---|---|---|
| `DISCORD_WEBHOOK_URL` | secret | — | required unless `--dry-run` |
| `ALERT_WEBHOOK_URL` | secret | — | optional, failure alerts |
| `CARD_LANG` | variable | `sq` | which language's feed/card to use |
| `HASHTAGS` | variable | `#Albania #FlamingoRevolution` | caption tail |
| `MAX_PER_RUN` | variable | `5` | cards posted per run once past first-run |
| `FIRST_RUN_POST` | variable | `3` | cards posted on the very first run |
| `FEED_URL` | variable | per `CARD_LANG` | comma-separated fallback list |
| `STATE_PATH` | env (workflow-set) | `state.json` | where state.json lives |
| `OUT_DIR` | env (workflow-set) | `out` | where `--dry-run` writes JPEGs |

## Behavior notes

- **First run** (empty state): posts only the `FIRST_RUN_POST` newest stories, and silently marks
  every other currently-live story as already-seen. This avoids dumping months of backlog into
  Discord the first time the workflow runs.
- **Later runs**: posts up to `MAX_PER_RUN` unseen stories, oldest-unseen first, so a backlog (e.g.
  from the workflow being paused) catches up gradually instead of flooding one run.
- **One bad story never kills a run**: if rendering or posting a single story fails, it's logged,
  skipped, and left **unseen** so a later run retries it; the rest of the batch still goes out.
- **Idempotent**: re-running against the same feed state posts nothing new — safe for GitHub to
  skip/delay/retry scheduled runs without risk of duplicate posts.

## Troubleshooting

- **Workflow didn't run on schedule**: GitHub can delay or skip scheduled runs under load, and
  disables scheduled workflows in public repos after ~60 days of repo inactivity. Actions tab →
  find `ig-cards` → **Enable workflow** if it shows as disabled, or just **Run workflow** manually.
- **"Could not read the feed. Last error: ..."**: the live JSON endpoint is down or changed shape.
  Check `https://flamingo-watch.com/data/articles-sq.json` loads in a browser. If the path
  changed, update the `FEED_URL` repo variable as a stopgap while the code catches up.
- **A card looks wrong (cut-off text, missing summary)**: summary is omitted by design when the
  site's AI step hasn't produced one yet for that story (`ai: false` in the source JSON) — not a
  bug. Title/summary truncate with `…` only when they genuinely exceed the card's line limits.
- **Nothing posted but the run succeeded**: either every current story was already `seen`, or it
  was a first run and everything except the newest 3 was seeded as seen on purpose.
- **Check what happened in a run**: Actions tab → the run → logs show fetch count, how many were
  unseen, how many posted, and any per-story errors (skipped, not fatal).
- **Check bot state directly**: open `state.json` on the `bot-state` branch on GitHub — plain
  JSON, no secrets, safe to read anytime.

## Rollback

- Disable the schedule without deleting anything: Actions tab → `ig-cards` → **⋯** → **Disable
  workflow**.
- The previous phase's script is always `scripts/cards_to_discord.py` on `main` at the last known
  good commit — revert the PR that introduced a regression rather than hand-editing forward.

## Safety ceiling (forward-looking)

There's no Instagram posting yet (Phase 3), but once there is: Instagram's hard API limit is 100
posts/24h; the plan is a safety ceiling of `MAX_PUBLISH_PER_DAY` default 50, well under that, so a
runaway bug can't burn the account. Not implemented yet — noted here so it isn't forgotten.
