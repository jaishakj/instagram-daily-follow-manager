# Instagram Daily Follow Manager (Linux)

This free helper extracts usernames from your Instagram JSON export and opens up to 10 profile pages per local calendar day.

**Important:** It does not automatically click Follow or Send Request. You perform that action yourself in the browser, then confirm it in the terminal. This avoids implementing unauthorized follow-bot behavior and lets you verify each account.

## Your file
- Extracted unique usernames: **1191**
- Input: `usernames.json`
- Progress: `progress.json` (created automatically)
- Browser session: `browser_profile/` (keeps your login session locally)

## Install on Zorin OS / Linux

Install Python 3 and pip if needed, then in this folder run:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
python main.py
```

If Linux reports missing Chromium system libraries, run:

```bash
python -m playwright install-deps chromium
```

On the first run, Instagram may ask you to log in in the opened browser. Log in only on the official `instagram.com` website. Do not paste your password or session cookies into scripts.

## How it works
1. Reads `usernames.json`.
2. Removes duplicates while preserving the original order.
3. Opens up to 10 profiles that are not yet marked complete.
4. You manually click Follow / Request (or verify the account is already followed/requested).
5. Type `y` in the terminal to mark it complete, `s` to skip, or `q` to stop.
6. It saves progress so future runs continue where you left off.

The daily limit is a local queue limit, not a guarantee that Instagram considers a particular follow rate safe. Avoid continuing if Instagram shows a restriction or warning.

## Reset progress
Stop the script and rename or delete `progress.json`. This resets only the local tracker, not Instagram follows or requests.
