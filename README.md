# klein-lister

> 🤖 **AI-generated:** this repository (code, workflow and docs) was created with
> [Claude Code](https://claude.com/claude-code). Review changes before relying on them.

Manage your [kleinanzeigen.de](https://www.kleinanzeigen.de) listings from a Git repo.
Each listing is a folder with an `ad.yaml` and its photos. Push and a GitHub
Actions workflow creates, updates or deletes the listings to match.

Under the hood it uses the open-source
[kleinanzeigen-bot](https://github.com/Second-Hand-Friends/kleinanzeigen-bot),
which drives a real Chromium browser (Kleinanzeigen has no public API).

> **Heads-up:** automating your account may violate the Kleinanzeigen terms of
> service. Use at your own risk; the worst case is a suspended account.

## How it's organised

This repo is the **tool**: scripts plus a
[reusable workflow](.github/workflows/sync.yml). It holds no listings.

Your listings live in **your own private data repo**, which contains your
`config.yaml`, a `listings/` folder, your login secrets and a short workflow
that calls this one. Your self-hosted runner is attached only to that private
repo, so nobody else can run code on it.

```
your-data-repo/
  config.yaml                    defaults for all listings (contact, postal code, shipping)
  listings/<item>/ad.yaml        one folder per listing, photos next to it
  imported-inactive/             imported listings that weren't active online, not synced
  .github/workflows/sync.yml     calls klein-lister's workflow
```

## Lifecycle

| You do this in the data repo | The workflow does this on Kleinanzeigen |
| --- | --- |
| Add `listings/<item>/ad.yaml` + photos | Publishes the listing and commits its `id` back into `ad.yaml` |
| Edit price, text or swap photos in that folder | Updates the listing in place (keeps watchers) |
| Set `active: false` (sold) | Deletes the listing and removes the `id` from `ad.yaml` |
| Delete the folder | Deletes the listing |
| Nothing (daily schedule) | Extends listings that expire within 8 days |
| Run the workflow with `import` | Downloads your existing listings (text, photos, id) into `listings/` |

Start from [`examples/gaming-laptop/ad.yaml`](examples/gaming-laptop/ad.yaml).
All fields are documented in the
[ad configuration reference](https://github.com/Second-Hand-Friends/kleinanzeigen-bot/blob/main/docs/AD_CONFIGURATION.md).

Don't edit the `id`, `content_hash`, `created_on` or `updated_on` fields; the bot maintains them.

## Setup

1. **Create a private data repo** and copy into it:
   - [`examples/config.yaml`](examples/config.yaml) → `config.yaml`, then fill in
     `ad_defaults.contact.name` and `zipcode`
   - [`examples/caller-workflow.yml`](examples/caller-workflow.yml) → `.github/workflows/sync.yml`
   - an empty `listings/` folder (e.g. `listings/.gitkeep`) and a `.gitignore` with `.runtime/`
2. **Add secrets** to the data repo under *Settings → Secrets and variables → Actions*:
   `KLEINANZEIGEN_USERNAME` and `KLEINANZEIGEN_PASSWORD`.
3. **Set up a self-hosted runner** for the data repo on a machine at home (Linux or
   macOS, always on, e.g. a Raspberry Pi 4/5 or a spare PC) with Chromium or Chrome,
   Python 3 and Git installed: *Settings → Actions → Runners → New self-hosted runner*,
   and add the label `kleinanzeigen`. Kleinanzeigen tends to challenge logins from
   GitHub's cloud IPs, while a home IP with a persistent browser profile usually
   stays logged in.
4. **Log in once by hand** on that machine, as the same user the runner runs as,
   with a screen attached (or over VNC):

   ```bash
   git clone https://github.com/killsometimebe4timekillsu/klein-lister
   git clone <your-data-repo>
   export KLEINANZEIGEN_BOT_USERNAME='you@example.com'
   export KLEINANZEIGEN_BOT_PASSWORD='...'
   bash klein-lister/scripts/login.sh <your-data-repo-folder>
   ```

   Solve any CAPTCHA or SMS check in the browser that opens. The session is kept in
   `~/.klein-lister/browser-profile` and reused by the workflow.
   Run it again whenever a sync fails at login. On a runner without a screen, use
   `login-remote.sh` instead, see [Logging in on a runner without a screen](#logging-in-on-a-runner-without-a-screen).

## Importing existing listings

Already have listings online? After the setup, run *Actions → Sync listings →
Run workflow* with `import` in the data repo. Every listing that is online but
not yet in the repo is downloaded to `listings/<title>_<id>/ad.yaml` with its
photos and committed. From then on the normal sync manages it. Running `import`
again only fetches listings that are missing from the repo.

Listings that aren't active online (paused, reserved or expired) land in
`imported-inactive/` instead, so a sync never mistakes them for sold items and
deletes them. Move a folder into `listings/` (with `active: true`) to manage it.

## Running manually

*Actions → Sync listings → Run workflow* with `sync` compares every listing by
content hash (note: a swapped photo with the same file name is only detected on
push), `extend` to extend expiring listings, or `import` (see above).

Locally, from the data repo, `python3 /path/to/klein-lister/scripts/sync.py --dry-run --before <sha>`
prints the bot commands a push since `<sha>` would run.

## If the login is blocked

Kleinanzeigen may answer a login with "IP-Bereich vorübergehend gesperrt" (the log
shows `STILL_ON_PASSWORD_PAGE + IP_RANGE_BLOCKED`). That is a temporary block of the
network range the request came from. Press reports and user forums say it also hits
ordinary users, for example behind shared (CGNAT) addresses or VPNs, and usually
lifts after some time. It doesn't mean your account is blocked.

What the workflow does about it: the run stops at the first blocked login, and
no further login is attempted for 6 hours (`KLEIN_LISTER_BLOCK_COOLDOWN_HOURS`), so
our own retries can't prolong the block. Runs during the cooldown are skipped with a
warning (a skipped daily `extend` stays green, a skipped `sync`/`import` is red so you
notice). A successful interactive login clears the cooldown, as does deleting
`~/.klein-lister/login-blocked` on the runner.

What you can do:
1. **Log in yourself on the runner** (next section). A login you complete by hand in the
   bot's browser profile is stored there, and the bot then reuses the session instead of
   logging in on every run. It also tells you whether the block is about the network
   (a human login is blocked too) or only about the unattended login.
2. **Check whether your IPv4 address is shared.** If the WAN IPv4 shown in your router
   differs from what `curl -4 ifconfig.me` prints on the runner, or starts with `100.64.`,
   your provider shares one address between many customers (CGNAT/DS-Lite).
3. **Ask Kleinanzeigen.** Use their help article on restricted IPs and the support form,
   and ask whether there is an approved interface for managing listings automatically.

## Logging in on a runner without a screen

`scripts/login-remote.sh` starts a virtual screen on the runner that you watch and
control over VNC, and runs `login.sh` on it. You type your credentials and solve any
CAPTCHA or SMS check yourself.

```bash
sudo apt install xvfb x11vnc
export KLEINANZEIGEN_BOT_USERNAME='you@example.com'   # only used to check it is the same account
export KLEINANZEIGEN_BOT_PASSWORD='unused'
bash klein-lister/scripts/login-remote.sh <your-data-repo-folder>
```

It prints a one-time VNC password. VNC listens on `localhost` only, so connect through
an SSH tunnel (`ssh -L 5900:localhost:5900 <runner>`, then a VNC viewer on
`localhost:5900`), or set `KLEIN_LISTER_VNC_LISTEN` to a private address such as the
runner's [Tailscale](https://tailscale.com) IP if you can't SSH into it directly.
When you're logged in, press ENTER in the terminal.

## Versions

The data repo calls the workflow at a tag (`@v1`) and passes the same tag as
`tool-ref`. Bump both together to pick up a new version.

## Layout of this repo

```
.github/workflows/sync.yml   reusable workflow (workflow_call)
scripts/sync.py              decides what to delete / publish / update / import
scripts/install-bot.sh       downloads the bot binary (KLEINANZEIGEN_BOT_VERSION, default latest)
scripts/login.sh             one-time interactive login on the runner
examples/                    config.yaml, caller-workflow.yml and a sample listing
```
