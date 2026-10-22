#!/usr/bin/env python3
"""
Daily Instagram profile queue.
Opens up to 10 profiles per local calendar day; the user manually performs
the Follow/Request action in the browser and confirms it in the terminal.
Does not click Follow automatically.
"""
import json
import os
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
USERNAMES_FILE = ROOT / "usernames.json"
PROGRESS_FILE = ROOT / "progress.json"
BROWSER_PROFILE = ROOT / "browser_profile"
DAILY_LIMIT = 10

def load_json(path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def save_progress(progress):
    temp = PROGRESS_FILE.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
    temp.replace(PROGRESS_FILE)

def main():
    usernames = load_json(USERNAMES_FILE, [])
    if not isinstance(usernames, list):
        raise SystemExit("usernames.json must contain a JSON list of usernames.")

    # Normalize and remove duplicates while preserving order.
    cleaned, seen = [], set()
    for value in usernames:
        username = str(value).strip().lstrip("@")
        key = username.lower()
        if username and key not in seen:
            cleaned.append(username)
            seen.add(key)
    usernames = cleaned

    progress = load_json(PROGRESS_FILE, {"completed": {}, "daily": {}})
    progress.setdefault("completed", {})
    progress.setdefault("daily", {})
    today = date.today().isoformat()
    done_today = int(progress["daily"].get(today, 0))

    pending = [u for u in usernames if u.lower() not in {
        k.lower() for k in progress["completed"].keys()
    }]

    if not pending:
        print(f"All {len(usernames)} usernames are marked complete.")
        return
    if done_today >= DAILY_LIMIT:
        print(f"Today's limit ({DAILY_LIMIT}) is already reached. Run again tomorrow.")
        return

    count = min(DAILY_LIMIT - done_today, len(pending))
    batch = pending[:count]
    print(f"Total usernames: {len(usernames)}")
    print(f"Marked complete: {len(progress['completed'])}")
    print(f"Remaining: {len(pending)}")
    print(f"Opening {len(batch)} profile(s) today. Click Follow/Request yourself.")
    print("After each profile, return to this terminal and enter:")
    print("  y = you completed the action (or it was already followed/requested)")
    print("  s = skip for now (not marked complete)")
    print("  q = stop for today")
    print("")

    BROWSER_PROFILE.mkdir(exist_ok=True)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE),
            headless=False,
            viewport={"width": 1280, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()

        for index, username in enumerate(batch, start=1):
            url = f"https://www.instagram.com/{quote(username)}/"
            print(f"[{index}/{len(batch)}] @{username} — {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            print("If prompted, log in normally in the browser. Do not share your password.")
            while True:
                answer = input("Mark complete? [y/s/q]: ").strip().lower()
                if answer in {"y", "s", "q"}:
                    break
                print("Please enter y, s, or q.")

            if answer == "y":
                progress["completed"][username] = {
                    "date": today,
                    "status": "user_confirmed",
                }
                progress["daily"][today] = int(progress["daily"].get(today, 0)) + 1
                save_progress(progress)
                print("Saved.")
            elif answer == "q":
                break
            else:
                print("Skipped; it will remain in the queue.")

            if progress["daily"].get(today, 0) >= DAILY_LIMIT:
                print("Daily limit reached.")
                break

        context.close()

    remaining = sum(
        1 for u in usernames
        if u.lower() not in {k.lower() for k in progress["completed"].keys()}
    )
    print(f"\nRemaining usernames: {remaining}")
    print(f"Progress saved to: {PROGRESS_FILE}")

if __name__ == "__main__":
    main()
