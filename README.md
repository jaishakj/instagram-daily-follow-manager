# Instagram Daily Follow Manager

Reads `usernames.json` (1191 handles) and, once per day, follows up to 10 of them.
Playwright drives a visible Chromium window and clicks Follow itself.

## Setup (Linux / macOS / Windows with a screen)
```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
python main.py --login           # log in ONCE in the browser window, then press Enter
```
Type your password only on the real instagram.com page in that window. It is never
read by the script. The session is stored in `browser_profile/` (git-ignored).

## Daily use
```bash
python main.py --dry-run   # first time: opens profiles, reports what it would do, never clicks
python main.py             # automatic: clicks Follow, max 10 follow actions per day
python main.py --limit 5   # lower the daily cap (hard max 20)
python main.py --manual    # old mode: you click, then confirm y/s/q in the terminal
```

## Safety behaviour
- Random 30-90 s pause between profiles; max 30 profiles opened per run.
- A follow only counts as done after the button visibly changes to Following/Requested.
- Stops immediately on an "Action Blocked" / "Try again later" style dialog. Wait 24-48 h.
- Stops if logged out, or after 3 unrecognised results in a row (Instagram changed its layout).
- Already followed / already requested / deleted accounts are marked done without a click.
- Progress is saved after every profile in `progress.json`; delete it to reset the local tracker.

## Run it every day automatically (Linux, cron)
A screen session is required because the browser is visible. Example, 10:00 daily:
```
0 10 * * * cd /path/to/instagram-daily-follow-manager && DISPLAY=:0 .venv/bin/python main.py >> run.log 2>&1
```

## Risks
Automated following violates Instagram's Terms of Use and can lead to action blocks or
account restriction, even at low volume. The selectors depend on Instagram's current page
layout and may need updating. Use at your own risk.
