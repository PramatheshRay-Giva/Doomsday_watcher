# BookMyShow ticket watcher: Avengers: Doomsday @ AMB Bengaluru, 17 Dec

This script opens AMB Cinemas' BookMyShow page for **17 Dec 2026** every ~3 minutes in a headless browser.
The page counts as live when **both** of these are true:

1. BookMyShow actually shows 17 Dec. If a date isn't open yet, BMS redirects you to the nearest open date.
2. "Doomsday" appears on that page.

When both hold, it sends a phone push and/or an email (with a screenshot), then stops.
If it gets blocked 10 times in a row, it also alerts you, so it can't fail silently.

It runs on **GitHub Actions**, so nothing needs to stay on at your end (see below).
You can also run it locally on any computer that stays awake (steps 1–4).

## Running on GitHub (no laptop needed)

`.github/workflows/watch.yml` starts a watcher run every hour. Each run checks every ~3 minutes for about 5.5 hours, and the next queued run takes over when it ends.
Once tickets are live, it alerts you and switches itself off.

1. Go to **Settings → Secrets and variables → Actions → New repository secret** and add:
   - `BMS_VENUE_URL`: the AMB link (see step 2 below)
   - `NTFY_TOPIC`: your ntfy topic, and/or
   - `SMTP_USER` + `SMTP_PASS`: Gmail address and App Password (optionally `EMAIL_TO` if alerts should go elsewhere)
2. Go to **Actions → BMS watcher → Run workflow** and choose `test-notify`. You should get a test alert.
3. Run it again with `once`, then open the run log. It should say `NOT_YET` with `date in URL: False`.
   If it says `BLOCKED`, BookMyShow is blocking GitHub's servers. In that case, run it locally on an always-on device instead (an old phone with Termux, a Raspberry Pi, etc.).
4. That's it. The hourly schedule keeps it going. Each run uploads a `last-check` screenshot you can look at.

## 1. Install (one time)

```bash
pip install playwright
```

```bash
python -m playwright install chromium
```

## 2. Get the AMB venue link

On in.bookmyshow.com: set the city to **Bengaluru**, open **Cinemas**, choose **AMB Cinemas (Kapali, Gandhinagar)** and click any date.
Copy the URL from the address bar. It ends in something like `/buytickets/XXXX/20261120`.
You don't need to change the date in it; the script swaps in 17 Dec itself.

## 3. Set up notifications (one or both)

**Phone push (easiest, free):** install the **ntfy** app (Android/iOS) and subscribe to a topic with a long random name, e.g. `doomsday-amb-x7k29q`.

**Email (Gmail):** create an App Password (Google Account → Security → 2-Step Verification → App passwords).

```bash
export NTFY_TOPIC="doomsday-amb-x7k29q"
export SMTP_USER="you@gmail.com"
export SMTP_PASS="abcdefghijklmnop"
export BMS_VENUE_URL="https://in.bookmyshow.com/cinemas/bengaluru/amb-.../buytickets/XXXX/20261120"
```

(Windows PowerShell: `$env:NTFY_TOPIC="..."` etc.)

## 4. Test, then run

```bash
python watch.py --test-notify
```
You should get a test push/email.

```bash
python watch.py --once
```
This prints what it saw and saves `last_check.png`. Right now it should say `NOT_YET` with `date in URL: False`.
If it says `BLOCKED`, try `--show` to watch the browser.

```bash
python watch.py
```
This keeps watching. Leave it running.

## Options

| Flag | Default | |
|---|---|---|
| `--date` | `20261217` | date to watch (YYYYMMDD) |
| `--movie` | `doomsday` | text that must appear on the page |
| `--interval` | `180` | seconds between checks (plus random 0–45s) |
| `--show` | off | show the browser window |

Please don't set the interval very low. Checking every few minutes is enough, and it's less likely to get you blocked.
