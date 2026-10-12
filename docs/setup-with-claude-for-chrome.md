# Setting up Runify with Claude in Chrome

This guide gets the app running on Google Cloud Run and connected to Strava,
Spotify and Claude. Each part has a prompt you can paste into Claude in
Chrome, which will drive the web pages for you. It stops and hands back to
you whenever you need to log in, approve a payment, or handle a secret.

**The one rule for secrets.** Client secrets, API keys and the setup key
must never be typed into a chat, including Claude in Chrome's. When a step
produces one, *you* copy it and paste it straight into Google Secret Manager.
The prompts below tell Claude in Chrome to stop at those moments.

Allow about an hour. Do the parts in order, because later parts need the
web address created in Part 3.

## What you'll end up with

| Thing | Where | Secret? |
| --- | --- | --- |
| App address, e.g. `https://runify-abc123-ew.a.run.app` | Cloud Run | No |
| Strava Client ID | strava.com/settings/api | No |
| Strava Client Secret | strava.com/settings/api | **Yes** |
| Spotify Client ID | developer.spotify.com/dashboard | No |
| Spotify Client Secret | developer.spotify.com/dashboard | **Yes** |
| Claude API key | platform.claude.com | **Yes** |
| Setup key (you invent it) | Secret Manager | **Yes** |
| Strava verify token (you invent it) | Secret Manager | **Yes** |

Make the two invented values long and random. In Google Cloud Shell,
`openssl rand -hex 24` prints one; run it twice.

---

## Part 1: GitHub repository (done)

The code lives in the private repository `tstpeter/runify`. Merging
its pull request into `main` is what Cloud Run will deploy.

---

## Part 2: Google Cloud project and database

**You first:** sign in to <https://console.cloud.google.com> with the Google
account you want to use. If you have never used Google Cloud, it will ask you
to set up billing. Cloud Run needs a billing account even though this app
stays inside the free tier; do that yourself.

**Paste into Claude in Chrome:**

> In the Google Cloud console tab, help me set up a project for a small
> personal web app.
>
> 1. Create a new project called `runify` and switch to it.
> 2. Enable these APIs: Cloud Run Admin API, Cloud Build API, Secret Manager
>    API, Cloud Firestore API, Artifact Registry API.
> 3. Open Firestore and create the `(default)` database in **Native mode**,
>    location `europe-west2 (London)`, with production security rules.
> 4. Open Billing, Budgets & alerts, and create a budget of £5 per month for
>    this project with email alerts at 50%, 90% and 100%.
>
> If any page asks me to accept terms or confirm billing, stop and ask me to
> do it. Tell me when all four are done.

---

## Part 3: Deploy the app on Cloud Run

**Paste into Claude in Chrome:**

> In the Google Cloud console, project `runify`, open Cloud Run and
> click **Deploy container**, then choose **Continuously deploy from a
> repository (source or function)** and **Set up with Cloud Build**.
>
> 1. Repository provider GitHub. If it asks to install or authorise the
>    Google Cloud Build GitHub app, stop and let me do that, then continue.
>    Choose repository `tstpeter/runify`.
> 2. Branch `^main$`, build type **Dockerfile**, source location
>    `/Dockerfile`.
> 3. Service name `runify`, region `europe-west1 (Belgium)`.
> 4. Authentication: **Allow unauthenticated invocations** (Strava and
>    Spotify must be able to reach it; the app checks its own keys).
> 5. Billing: **Instance-based** (this is the setting called "CPU is always
>    allocated" in older screens). The app does its work after replying to
>    Strava, so it needs CPU between requests.
> 6. Scaling: minimum instances 0, maximum instances 1.
> 7. Under Container, Variables & Secrets, add the environment variable
>    `STORE_BACKEND` = `firestore` for now. We'll add the rest later.
> 8. Click Create and wait for the first deployment to finish.
>
> When it's live, open `<service URL>/health` in a new tab and check it shows
> `{"ok":true}`. Then tell me the service URL. Don't open anything else.

Write down the service URL. From here on it's called **BASE_URL**, and the
part without `https://` is the **host**.

**Paste into Claude in Chrome:**

> In the Google Cloud console, open IAM & Admin, IAM. Find the service
> account Cloud Run is using for `runify` (shown on the service's
> Security tab, usually ending `-compute@developer.gserviceaccount.com`).
> Give it two roles: **Cloud Datastore User** and **Secret Manager Secret
> Accessor**. Tell me when done.

---

## Part 4: Register the Strava app

**Paste into Claude in Chrome** (replace the host first):

> Open <https://www.strava.com/settings/api>. If I'm not logged in, stop and
> let me log in. Create an API application with:
>
> - Application name: `Runify (personal)`
> - Category: `Other`
> - Club: leave empty
> - Website: `https://peterfotheringham.com`
> - Application description: `Names my runs with the soundtrack and weather.`
> - Authorization Callback Domain: `HOST GOES HERE` (host only, no
>   `https://`, no path)
>
> If it asks for an app icon, stop and let me upload one. After saving, tell
> me the **Client ID** only. Do **not** reveal, copy or read out the Client
> Secret; just tell me where on the page it is.

**You do this:** click to show the Client Secret and keep the tab open for
Part 7.

---

## Part 5: Register the Spotify app

**Paste into Claude in Chrome** (replace BASE_URL first):

> Open <https://developer.spotify.com/dashboard>. If I'm not logged in, stop
> and let me log in. If it asks me to accept the developer terms, stop and
> let me do it. Create an app with:
>
> - App name: `Runify`
> - App description: `Turns the songs from each run into a playlist.`
> - Website: `https://peterfotheringham.com`
> - Redirect URI: `BASE_URL GOES HERE/callback/spotify` (click Add)
> - Which API/SDKs: tick **Web API** only
>
> Save. Then open the app's Settings and tell me the **Client ID** only. Do
> not reveal or read out the Client Secret. Finally open the app's User
> Management tab and tell me whether my own Spotify account is listed; if
> it isn't, stop and let me add myself.

**You do this:** click "View client secret" and keep the tab open for Part 7.

---

## Part 6: Claude API key

**You do this yourself** (the key is shown once):

1. Go to <https://platform.claude.com>, sign in, open **API keys** and create
   a key called `runify`.
2. Copy it straight into Part 7. Don't paste it anywhere else.
3. Under **Limits**, set a monthly spend limit, for example £5. The app uses
   roughly 1 to 2p per run.

---

## Part 7: Put the secrets into Secret Manager

**Paste into Claude in Chrome:**

> In the Google Cloud console, project `runify`, open Secret
> Manager. I need five secrets, created one at a time:
> `STRAVA_CLIENT_SECRET`, `SPOTIFY_CLIENT_SECRET`, `ANTHROPIC_API_KEY`,
> `SETUP_KEY`, `STRAVA_VERIFY_TOKEN`.
>
> For each one: click Create secret, type the name, then **stop and let me
> paste the value myself**. Do not look at, read out or repeat the value.
> When I say "done", click Create and move on to the next name.

**You do this:** paste each value when asked (the two secrets from Strava
and Spotify, the Claude key, and your two invented values).

---

## Part 8: Give the app its settings

**Paste into Claude in Chrome** (replace the three values first):

> In Cloud Run, open the `runify` service and click **Edit & deploy
> new revision**. Under Container, Variables & Secrets:
>
> Environment variables (keep `STORE_BACKEND=firestore`):
> - `BASE_URL` = `BASE_URL GOES HERE`
> - `STRAVA_CLIENT_ID` = `STRAVA CLIENT ID GOES HERE`
> - `SPOTIFY_CLIENT_ID` = `SPOTIFY CLIENT ID GOES HERE`
>
> Secrets exposed as environment variables, each using version `latest`,
> with the variable name the same as the secret name:
> `STRAVA_CLIENT_SECRET`, `SPOTIFY_CLIENT_SECRET`, `ANTHROPIC_API_KEY`,
> `SETUP_KEY`, `STRAVA_VERIFY_TOKEN`.
>
> Deploy, wait for it to finish, then check `/health` still shows
> `{"ok":true}`.

---

## Part 9: Connect everything

**You do this** (it involves your setup key, so keep it out of the chat):

1. Open `BASE_URL/?key=YOUR_SETUP_KEY`. You'll see a small setup page.
2. Click **connect** next to Strava. Approve, and make sure the box allowing
   the app to **upload/update your activities** is ticked.
3. Click **connect** next to Spotify and approve.
4. Click **check or create** next to the Strava webhook. You should see
   `"status": "subscribed"`.
5. Don't bookmark the setup page: the key in its address works like a password.

## Part 10: Switch off Bandók

Log in at <https://www.bandok.com>, open your account page and click
**Disable Activity Naming** (you can keep the account). Otherwise both apps
will try to rename each run.

## Part 11: Try it

- **Quick test without running:** on Strava, open any recent run and rename it
  to `Morning Run`. Within a minute or so it should get a new name and
  description. (An old run won't have a soundtrack, because Spotify only
  remembers your last 50 plays.)
- **Reroll:** add ` :(` to the end of the new name and save.
- **Real test:** go for a run with Spotify playing and upload as normal.

If nothing happens, open Cloud Run, `runify`, **Logs**. Each run
logs a line like `Activity 123: named: ...` or the reason it was skipped.

---

## Optional: use runs.peterfotheringham.com

The `run.app` address works fine forever. If you'd rather use your own
domain:

1. In Cloud Run, **Manage custom domains**, add a mapping for
   `runs.peterfotheringham.com` to `runify`. Google will ask you to
   verify you own the domain.
2. At whoever sells you `peterfotheringham.com`, add the DNS record Google
   shows (a `CNAME` to `ghs.googlehosted.com`). Certificates can take up to
   a day.
3. Then update three things to the new address: `BASE_URL` on Cloud Run, the
   Strava Authorization Callback Domain, and the Spotify Redirect URI.
4. Delete and recreate the Strava webhook (Strava allows one): ask me and
   I'll add a button for it.

Claude in Chrome can do steps 1 and 3 with a prompt like the ones above. For
step 2, tell me who your domain registrar is and I'll write that prompt too.
