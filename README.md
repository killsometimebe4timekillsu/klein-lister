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
repo, so nobody else can run code on it. To run your own copy of the tool, see
[Using your own fork](#using-your-own-fork-two-repositories).

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
4. **Do the [one-time manual login](#one-time-manual-login-required).** This step is
   required: until a person has logged in once in the runner's browser profile, the
   workflow's first login will most likely fail.

## Using your own fork (two repositories)

To use this for your own account, set up two repositories, as this project does:

| Repo | Visibility | Holds |
| --- | --- | --- |
| Your **fork** of klein-lister | public (a fork of a public repo stays public) | the scripts and the reusable workflow, no personal data |
| Your **data repo** (a new, empty repo, not a fork) | **private** | `config.yaml`, `listings/`, the secrets, the caller workflow and the self-hosted runner |

Why two: your listings carry your name, address, phone number and photos, and the runner
holds your logged-in session, so all of that must stay private. The tool itself is generic
code. Why a fork rather than the original: the workflow runs on your runner with access to
your Kleinanzeigen login, so a repo you control (or a commit you reviewed) decides what code
gets there, and changes in the original reach you only when you pull them in.

1. **Fork** this repo on GitHub. Create the ref you will pin to, for example
   `git tag v1 && git push origin v1`, or use a full commit SHA that you reviewed.
2. **Create the data repo as private** and follow [Setup](#setup) above.
3. **Point the caller workflow at your fork.** In the data repo's `.github/workflows/sync.yml`,
   change the tool in three places:
   ```yaml
   jobs:
     sync:
       uses: <you>/klein-lister/.github/workflows/sync.yml@v1
       with:
         tool-repository: <you>/klein-lister
         tool-ref: v1
   ```
   `uses:` selects the workflow file, while `tool-repository` and `tool-ref` select the scripts
   it runs. They must name the same repo and the same ref, or the workflow of one version runs
   the scripts of another (the defaults point to the original repo).
4. **If your fork is private,** allow the data repo to use its workflows: fork → *Settings →
   Actions → General → Access*.
5. **To update,** use *Sync fork* on GitHub, review the changes and move your ref (or bump the
   SHA) when you are happy.

Never attach the self-hosted runner to a public repo: pull requests from strangers could run
code on it. Keep listings out of the fork, since it is public.

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
1. **Log in yourself on the runner** (see [One-time manual login](#one-time-manual-login-required)). A login you complete by hand in the
   bot's browser profile is stored there, and the bot then reuses the session instead of
   logging in on every run. It also tells you whether the block is about the network
   (a human login is blocked too) or only about the unattended login.
2. **Check whether your IPv4 address is shared.** If the WAN IPv4 shown in your router
   differs from what `curl -4 ifconfig.me` prints on the runner, or starts with `100.64.`,
   your provider shares one address between many customers (CGNAT/DS-Lite).
3. **Ask Kleinanzeigen.** Use their help article on restricted IPs and the support form,
   and ask whether there is an approved interface for managing listings automatically.

## When a run fails

The Actions log of the *Sync* step shows the bot's output. For more detail, add a
repository variable `KLEIN_LISTER_VERBOSE` with the value `1` in the data repo
(*Settings → Secrets and variables → Actions → Variables*). The bot then runs with
`-v` and logs its debug output; remove the variable again afterwards. The same log is
written to `.runtime/kleinanzeigen-bot-latest.log` in the data repo checkout on the runner.

An imported listing can come with `shipping_type: NOT_APPLICABLE`. On update Kleinanzeigen may
then reject the form with `Bitte wähle mindestens eine Versandoption aus`. Nothing is changed
online in that case. Set `shipping_type: PICKUP`, or `SHIPPING` together with `shipping_options`,
in that listing's `ad.yaml`.

If the log says `Manual recovery required` for a listing, the bot clicked "submit" but
couldn't confirm the result (typically a browser protocol error while Kleinanzeigen's
confirmation page loads, although the page was the "edit successful" one), and it never
retries by itself, because a repeated *publish* could create a duplicate listing. For an
*update* the workflow repeats it for exactly those listings (twice at most,
`KLEIN_LISTER_UPDATE_RETRIES`), since an update edits the same listing by id. The log then
shows a warning `Repeating it: attempt 1/2`, and the retry writes the new `content_hash` back.
A `publish` is never repeated: look at *Meine Anzeigen* to see whether the listing exists.
Note that a `sync` started by hand compares content hashes and also updates every listing
whose stored hash differs from what the bot computes now, not only the ones you changed.

## One-time manual login (required)

**Why it is needed.** The first login to Kleinanzeigen has to be done by a person. In
practice an unattended login from the runner was answered with "IP-Bereich vorübergehend
gesperrt", and a login can also demand a CAPTCHA, an SMS code or an e-mail verification
that only you can complete. Once you have logged in by hand in the bot's browser profile
(`~/.klein-lister/browser-profile` of the runner user), every later run reuses that saved
session and doesn't log in again. Skip this and the first run fails at login, and
further logins then pause for 6 hours (see [If the login is blocked](#if-the-login-is-blocked)).

**When to repeat it.** When the session has expired or was removed (the run log shows
`Logging in...` followed by a failure, or the cooldown warning), after deleting the
profile directory, or when you move the runner to another machine or user.

**Steps** (runner without a screen, reached over SSH; the runner service user is called
`ci` below):

1. **Prepare the runner** (once):
   ```bash
   sudo apt install xvfb x11vnc
   git clone https://github.com/killsometimebe4timekillsu/klein-lister ~/klein-lister
   ```
   The script also needs the folder of your data repo (the one with `config.yaml`). If the
   runner has already run the workflow, reuse its checkout:
   `/home/ci/actions-runner/_work/<data-repo>/<data-repo>/data`. Otherwise clone your data
   repo and use that.
2. **Make sure no workflow run is active** on the runner: Chromium can't share a profile
   between two processes.
3. **Open an SSH session with a tunnel for the screen** from your computer. The login
   command waits for ENTER, so it needs this interactive terminal:
   ```bash
   ssh -L 5900:localhost:5900 ci@<runner>
   # via a jump host, e.g. a Proxmox node:
   ssh -J <you>@<jump-host> -L 5900:localhost:5900 ci@<runner>
   ```
4. **In that session, start the virtual screen and the login:**
   ```bash
   git -C ~/klein-lister pull            # if you cloned it earlier
   bash ~/klein-lister/scripts/login-remote.sh <data-repo-folder>
   ```
   It asks for your Kleinanzeigen e-mail address (it must be the account you log into) and
   prints a one-time VNC password. You type the real password into the browser yourself, so
   it is never stored on the runner or in its shell history. Don't `export` it there.
5. **Connect a VNC viewer to `localhost:5900`** on your computer (macOS: Finder → Go →
   Connect to Server → `vnc://localhost:5900`; Windows/Linux: TigerVNC or Remmina) and
   enter that password. You see the bot's Chromium.
6. **Log in to Kleinanzeigen in that window** with your own credentials and complete any
   CAPTCHA, SMS or e-mail check. Wait until you see your logged-in pages (for example
   "Meine Anzeigen").
7. **Press ENTER in the SSH session.** The bot checks that it is the configured account,
   closes the browser to save the session, and clears the login-block cooldown.
8. **Run the workflow**: Actions → Sync listings → Run workflow → `import` the first
   time, `sync` afterwards. The log should show no `Logging in...` step, because the saved
   session is used.

If you are logging in at the runner itself (it has a screen), skip steps 1 to 5 and run
`bash ~/klein-lister/scripts/login.sh <data-repo-folder>` instead. If you can't reach the
runner over SSH but can over [Tailscale](https://tailscale.com), set
`KLEIN_LISTER_VNC_LISTEN` to the runner's Tailscale IP and connect the viewer to that
address instead of `localhost`.

If your own login in that browser is blocked as well, the network range is the problem,
not the unattended login: see [If the login is blocked](#if-the-login-is-blocked).

## Versions

The data repo calls the workflow at a ref (`@v1`) and passes the same ref as `tool-ref`.
Bump both together to pick up a new version. In the original repo `v1` is a branch that is
moved to the latest reviewed `main`; in your own fork you can pin a tag or a commit SHA instead
(see [Using your own fork](#using-your-own-fork-two-repositories)).

## Layout of this repo

```
.github/workflows/sync.yml   reusable workflow (workflow_call)
scripts/sync.py              decides what to delete / publish / update / import
scripts/install-bot.sh       downloads the bot binary (KLEINANZEIGEN_BOT_VERSION, default latest)
scripts/login.sh             one-time interactive login on the runner
scripts/login-remote.sh      the same over a virtual screen + VNC, for a runner without a monitor
examples/                    config.yaml, caller-workflow.yml and a sample listing
```
