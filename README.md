# klein-lister

> 🤖 **AI-generated:** this repository (code, workflow and docs) was created with
> [Claude Code](https://claude.com/claude-code). Review changes before relying on them.

Manage your [kleinanzeigen.de](https://www.kleinanzeigen.de) listings from this repo.
Each listing is a folder with an `ad.yaml` and its photos. Push to `main` and a
GitHub Actions workflow creates, updates or deletes the listings to match.

Under the hood it uses the open-source
[kleinanzeigen-bot](https://github.com/Second-Hand-Friends/kleinanzeigen-bot),
which drives a real Chromium browser (Kleinanzeigen has no public API).

> **Heads-up:** automating your account may violate the Kleinanzeigen terms of
> service. Use at your own risk; the worst case is a suspended account.

## Lifecycle

| You do this in the repo | The workflow does this on Kleinanzeigen |
| --- | --- |
| Add `listings/<item>/ad.yaml` + photos | Publishes the listing and commits its `id` back into `ad.yaml` |
| Edit price, text or swap photos in that folder | Updates the listing in place (keeps watchers) |
| Set `active: false` (sold) | Deletes the listing and removes the `id` from `ad.yaml` |
| Delete the folder | Deletes the listing |
| Nothing (daily schedule) | Extends listings that expire within 8 days |

Start from [`examples/gaming-laptop/ad.yaml`](examples/gaming-laptop/ad.yaml).
All fields are documented in the
[ad configuration reference](https://github.com/Second-Hand-Friends/kleinanzeigen-bot/blob/main/docs/AD_CONFIGURATION.md).
Defaults for every listing (contact name, postal code, shipping) live in
[`config.yaml`](config.yaml).

Don't edit the `id`, `content_hash`, `created_on` or `updated_on` fields; the bot maintains them.

## Setup

1. **Make the repo private.** Your listings, name and postal code live here, and
   a self-hosted runner on a public repo can be abused by pull requests from forks.
2. **Add secrets** under *Settings → Secrets and variables → Actions*:
   `KLEINANZEIGEN_USERNAME` and `KLEINANZEIGEN_PASSWORD`.
3. **Fill in `config.yaml`**: `ad_defaults.contact.name` and `zipcode`.
4. **Set up a self-hosted runner** on a machine at home (Linux or macOS, always on,
   e.g. a Raspberry Pi 4/5 or a spare PC) with Chromium or Chrome and Python 3 installed:
   *Settings → Actions → Runners → New self-hosted runner*, and add the label
   `kleinanzeigen`. Kleinanzeigen tends to challenge logins from GitHub's cloud IPs,
   while a home IP with a persistent browser profile usually stays logged in.
5. **Log in once by hand** on that machine, as the same user the runner runs as,
   with a screen attached (or over VNC):

   ```bash
   export KLEINANZEIGEN_BOT_USERNAME='you@example.com'
   export KLEINANZEIGEN_BOT_PASSWORD='...'
   bash scripts/login.sh
   ```

   Solve any CAPTCHA or SMS check in the browser that opens. The session is kept in
   `~/.klein-lister/browser-profile` and reused by the workflow.
   Run it again whenever a sync fails at login.

## Running manually

*Actions → Sync listings → Run workflow* with `sync` compares every listing by
content hash (note: a swapped photo with the same file name is only detected on
push), or `extend` to extend expiring listings.

Locally, `python3 scripts/sync.py --dry-run --before <sha>` prints the bot
commands a push since `<sha>` would run.

## Layout

```
config.yaml               bot config (defaults for all listings)
listings/<item>/ad.yaml   one folder per listing, photos next to it
examples/                 templates, not synced
scripts/sync.py           decides what to delete / publish / update
scripts/install-bot.sh    downloads the bot binary (KLEINANZEIGEN_BOT_VERSION, default latest)
scripts/login.sh          one-time interactive login on the runner
.github/workflows/sync.yml
```
