#!/usr/bin/env python3
"""
Instagram daily follow queue.

Default: Playwright drives a visible Chromium window and clicks Follow itself,
at most DAILY_LIMIT real follow actions per local calendar day, with random
delays. It stops immediately on any block/restriction warning.
--manual keeps the old mode where you click Follow yourself.
"""
import argparse
import json
import random
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
USERNAMES_FILE = ROOT / "usernames.json"
PROGRESS_FILE = ROOT / "progress.json"
BROWSER_PROFILE = ROOT / "browser_profile"

DAILY_LIMIT = 10          # follow actions per day (default)
HARD_MAX_LIMIT = 20       # --limit can never exceed this
MAX_VISITS_PER_RUN = 30   # profiles opened per run, incl. already-followed
MIN_DELAY, MAX_DELAY = 30, 90   # seconds between profiles
MAX_CONSECUTIVE_FAILURES = 3

RE_FOLLOW = re.compile(r"^(Follow|Follow Back)$", re.I)
RE_FOLLOWING = re.compile(r"^Following$", re.I)
RE_REQUESTED = re.compile(r"^Requested$", re.I)
RE_BLOCK = re.compile(
    r"action blocked|try again later|we restrict certain activity|"
    r"temporarily blocked|suspicious activity|confirm it'?s you",
    re.I,
)
RE_NOT_FOUND = re.compile(r"this page isn'?t available|user not found", re.I)


def sleep(seconds):
    time.sleep(seconds)


# ---------- progress ----------
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


def clean_usernames(raw):
    cleaned, seen = [], set()
    for value in raw:
        username = str(value).strip().lstrip("@")
        key = username.lower()
        if username and key not in seen:
            cleaned.append(username)
            seen.add(key)
    return cleaned


# ---------- page inspection (small helpers so tests can fake them) ----------
def has_button(page, pattern):
    return page.locator("header").get_by_role("button", name=pattern).count() > 0


def is_blocked(page):
    return page.get_by_role("dialog").filter(has_text=RE_BLOCK).count() > 0


def is_not_found(page):
    return page.get_by_text(RE_NOT_FOUND).count() > 0


def classify_and_follow(page, dry_run=False):
    """Returns one of: followed, requested, already_following, already_requested,
    unavailable, login_required, blocked, unknown, would_follow."""
    if "/accounts/login" in page.url:
        return "login_required"
    page.wait_for_timeout(2500)
    if is_blocked(page):
        return "blocked"
    if is_not_found(page):
        return "unavailable"
    if has_button(page, RE_FOLLOWING):
        return "already_following"
    if has_button(page, RE_REQUESTED):
        return "already_requested"
    if not has_button(page, RE_FOLLOW):
        return "unknown"
    if dry_run:
        return "would_follow"

    page.locator("header").get_by_role("button", name=RE_FOLLOW).first.click(timeout=10000)
    for _ in range(8):  # up to ~8s for the UI to confirm
        page.wait_for_timeout(1000)
        if is_blocked(page):
            return "blocked"
        if has_button(page, RE_REQUESTED):
            return "requested"
        if has_button(page, RE_FOLLOWING):
            return "followed"
    return "unknown"


# ---------- runners ----------
def open_context(p):
    BROWSER_PROFILE.mkdir(exist_ok=True)
    return p.chromium.launch_persistent_context(
        user_data_dir=str(BROWSER_PROFILE),
        headless=False,
        viewport={"width": 1280, "height": 900},
    )


def do_login(sync_playwright):
    with sync_playwright() as p:
        context = open_context(p)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.instagram.com/accounts/login/", timeout=60000)
        print("Log in in the browser window (official instagram.com page only).")
        input("When you can see your Instagram feed, press Enter here to save the session... ")
        context.close()
    print("Session saved in browser_profile/.")


def run_auto(sync_playwright, usernames, progress, limit, dry_run):
    today = date.today().isoformat()
    done_today = int(progress["daily"].get(today, 0))
    completed = {k.lower() for k in progress["completed"]}
    pending = [u for u in usernames if u.lower() not in completed]
    if not pending:
        print(f"All {len(usernames)} usernames are done.")
        return
    if done_today >= limit and not dry_run:
        print(f"Today's limit ({limit}) already reached ({done_today}). Run again tomorrow.")
        return

    print(f"Total: {len(usernames)} | done: {len(completed)} | pending: {len(pending)}")
    print(f"Follow actions today: {done_today}/{limit}" + ("  [DRY RUN, no clicks]" if dry_run else ""))

    failures, visits = 0, 0
    with sync_playwright() as p:
        context = open_context(p)
        page = context.pages[0] if context.pages else context.new_page()
        for username in pending:
            if visits >= MAX_VISITS_PER_RUN:
                print("Visit cap for this run reached.")
                break
            if not dry_run and int(progress["daily"].get(today, 0)) >= limit:
                print("Daily limit reached.")
                break
            visits += 1
            url = f"https://www.instagram.com/{quote(username)}/"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                status = classify_and_follow(page, dry_run=dry_run)
            except Exception as exc:  # network/timeouts/click errors
                print(f"@{username}: error {type(exc).__name__}: {exc}")
                status = "unknown"
            print(f"@{username}: {status}")

            if status in ("blocked", "login_required"):
                msg = ("Instagram showed a restriction warning. Stopping now. "
                       "Do not retry for at least 24-48 hours."
                       if status == "blocked" else
                       "Not logged in. Run: python main.py --login")
                print(msg)
                break

            if dry_run:
                continue

            if status in ("followed", "requested"):
                progress["completed"][username] = {"date": today, "status": status}
                progress["daily"][today] = int(progress["daily"].get(today, 0)) + 1
                failures = 0
                save_progress(progress)
            elif status in ("already_following", "already_requested", "unavailable"):
                progress["completed"][username] = {"date": today, "status": status}
                failures = 0
                save_progress(progress)
            else:  # unknown
                failures += 1
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    print(f"{MAX_CONSECUTIVE_FAILURES} unrecognised results in a row. "
                          "Instagram's layout may have changed. Stopping.")
                    break

            sleep(random.uniform(MIN_DELAY, MAX_DELAY))
        context.close()

    remaining = sum(1 for u in usernames if u.lower() not in {k.lower() for k in progress["completed"]})
    print(f"\nRemaining: {remaining} | Progress: {PROGRESS_FILE}")


def run_manual(sync_playwright, usernames, progress):
    today = date.today().isoformat()
    done_today = int(progress["daily"].get(today, 0))
    completed = {k.lower() for k in progress["completed"]}
    pending = [u for u in usernames if u.lower() not in completed]
    if not pending:
        print(f"All {len(usernames)} usernames are marked complete.")
        return
    if done_today >= DAILY_LIMIT:
        print(f"Today's limit ({DAILY_LIMIT}) is already reached. Run again tomorrow.")
        return

    batch = pending[:min(DAILY_LIMIT - done_today, len(pending))]
    print(f"Total usernames: {len(usernames)}")
    print(f"Marked complete: {len(progress['completed'])}")
    print(f"Remaining: {len(pending)}")
    print(f"Opening {len(batch)} profile(s) today. Click Follow/Request yourself.")
    print("  y = done (or already followed/requested), s = skip, q = stop\n")

    with sync_playwright() as p:
        context = open_context(p)
        page = context.pages[0] if context.pages else context.new_page()
        for index, username in enumerate(batch, start=1):
            url = f"https://www.instagram.com/{quote(username)}/"
            print(f"[{index}/{len(batch)}] @{username} {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            while True:
                answer = input("Mark complete? [y/s/q]: ").strip().lower()
                if answer in {"y", "s", "q"}:
                    break
                print("Please enter y, s, or q.")
            if answer == "y":
                progress["completed"][username] = {"date": today, "status": "user_confirmed"}
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

    remaining = sum(1 for u in usernames if u.lower() not in {k.lower() for k in progress["completed"]})
    print(f"\nRemaining usernames: {remaining}\nProgress saved to: {PROGRESS_FILE}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Instagram daily follow queue")
    ap.add_argument("--login", action="store_true", help="log in once and save the browser session")
    ap.add_argument("--manual", action="store_true", help="you click Follow yourself (old mode)")
    ap.add_argument("--dry-run", action="store_true", help="open profiles and report, never click")
    ap.add_argument("--limit", type=int, default=DAILY_LIMIT,
                    help=f"follow actions per day (default {DAILY_LIMIT}, max {HARD_MAX_LIMIT})")
    args = ap.parse_args(argv)
    limit = max(1, min(args.limit, HARD_MAX_LIMIT))

    from playwright.sync_api import sync_playwright

    if args.login:
        do_login(sync_playwright)
        return

    raw = load_json(USERNAMES_FILE, [])
    if not isinstance(raw, list):
        raise SystemExit("usernames.json must contain a JSON list of usernames.")
    usernames = clean_usernames(raw)
    progress = load_json(PROGRESS_FILE, {"completed": {}, "daily": {}})
    progress.setdefault("completed", {})
    progress.setdefault("daily", {})

    if args.manual:
        run_manual(sync_playwright, usernames, progress)
    else:
        run_auto(sync_playwright, usernames, progress, limit, args.dry_run)


if __name__ == "__main__":
    main()
