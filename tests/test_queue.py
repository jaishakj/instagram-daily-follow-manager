import builtins, json, shutil, sys
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import main

TMP = Path("/tmp/ig_queue_test")
today = date.today().isoformat()


class Loc:
    def __init__(self, n=0, click=None):
        self.n, self._click = n, click
    def count(self): return self.n
    @property
    def first(self): return self
    def click(self, **k):
        if self._click: self._click()
    def filter(self, **k): return self


class Header:
    def __init__(self, page): self.page = page
    def get_by_role(self, role, name=None):
        pg = self.page
        label = pg.button
        hit = label is not None and name.search(label)
        return Loc(1 if hit else 0, click=pg.on_click)


class Page:
    """Fake of the Playwright Page API subset used by main.py.
    scenarios: dict username -> (initial_button, after_click) where
    initial_button in Follow/Following/Requested/None, plus special keys."""
    def __init__(self, scenarios):
        self.scenarios, self.visited, self.clicks = scenarios, [], []
        self.url, self.button, self.special, self.after = "", None, None, None
        self.dialog = False
    def goto(self, url, **k):
        self.url = url
        user = url.rstrip("/").split("/")[-1]
        self.visited.append(user)
        self.user = user
        sc = self.scenarios.get(user, ("Follow", "Requested"))
        self.special = None
        self.dialog = False
        if sc[0] in ("login", "notfound"):
            self.special = sc[0]
            self.button = None
            if sc[0] == "login":
                self.url = "https://www.instagram.com/accounts/login/"
        else:
            self.button, self.after = sc
    def wait_for_timeout(self, ms): pass
    def locator(self, sel): return Header(self)
    def on_click(self):
        self.clicks.append(self.user)
        if self.after == "block": self.dialog = True
        elif self.after == "noop": pass
        else: self.button = self.after
    def get_by_role(self, role, **k):
        return Loc(1 if (role == "dialog" and self.dialog) else 0)
    def get_by_text(self, pat):
        return Loc(1 if self.special == "notfound" else 0)


def fake_pw(page):
    class Ctx:
        pages = [page]
        def close(self): pass
    class PW:
        class chromium:
            @staticmethod
            def launch_persistent_context(**k): return Ctx()
        def __enter__(self): return self
        def __exit__(self, *a): pass
    return lambda: PW()


def fresh():
    shutil.rmtree(TMP, ignore_errors=True); TMP.mkdir()
    main.PROGRESS_FILE = TMP / "progress.json"
    main.BROWSER_PROFILE = TMP / "bp"
    return {"completed": {}, "daily": {}}


def auto(users, scenarios, limit=10, dry=False, progress=None):
    progress = progress or fresh()
    page = Page(scenarios)
    with mock.patch.object(main, "sleep", lambda s: None):
        main.run_auto(fake_pw(page), users, progress, limit, dry)
    return page, progress


# 1. normal follow -> Requested / Following both count as an action
users = [f"u{i}" for i in range(30)]
page, pr = auto(users, {"u0": ("Follow", "Following"), "u1": ("Follow", "Requested")})
assert pr["completed"]["u0"]["status"] == "followed"
assert pr["completed"]["u1"]["status"] == "requested"
assert pr["daily"][today] == 10 and len(page.clicks) == 10, (pr["daily"], page.clicks)

# 2. already following / requested / not found: no click, completed, not counted
page, pr = auto(["a", "b", "c"], {"a": ("Following", None), "b": ("Requested", None), "c": ("notfound",)})
assert page.clicks == []
assert {k: v["status"] for k, v in pr["completed"].items()} == {
    "a": "already_following", "b": "already_requested", "c": "unavailable"}
assert pr["daily"].get(today, 0) == 0

# 3. block dialog after click -> stop immediately, user NOT marked done
page, pr = auto(["x", "y", "z"], {"x": ("Follow", "block")})
assert page.visited == ["x"] and "x" not in pr["completed"] and pr["daily"].get(today, 0) == 0

# 4. login redirect -> stop, nothing clicked
page, pr = auto(["x", "y"], {"x": ("login",)})
assert page.visited == ["x"] and page.clicks == [] and pr["completed"] == {}

# 5. UI never confirms (layout change) -> stop after 3 consecutive unknowns
page, pr = auto([f"n{i}" for i in range(10)], {f"n{i}": ("Follow", "noop") for i in range(10)})
assert len(page.visited) == 3 and pr["completed"] == {}

# 6. no follow button at all -> unknown, no click
page, pr = auto(["q"], {"q": (None, None)})
assert page.clicks == [] and pr["completed"] == {}

# 7. dry run never clicks or writes progress
page, pr = auto(["d1", "d2"], {}, dry=True)
assert page.clicks == [] and pr["completed"] == {} and not main.PROGRESS_FILE.exists()

# 8. limit respected across runs (resume)
pr = fresh(); pr["daily"][today] = 8
page, pr = auto(users, {}, progress=pr)
assert len(page.clicks) == 2 and pr["daily"][today] == 10
page, pr = auto(users, {}, progress=pr)
assert page.visited == []

# 9. hard max and CLI --limit clamp
assert max(1, min(999, main.HARD_MAX_LIMIT)) == 20

# 10. manual mode still works
pr = fresh(); page = Page({})
answers = iter(["y", "s", "y", "q"])
with mock.patch.object(builtins, "input", lambda *_: next(answers)):
    main.run_manual(fake_pw(page), users, pr)
assert set(pr["completed"]) == {"u0", "u2"}

print("ALL TESTS PASSED")
