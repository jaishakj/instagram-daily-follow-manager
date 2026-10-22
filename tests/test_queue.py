import sys, json, builtins, shutil
from pathlib import Path
from unittest import mock
from datetime import date
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
visited=[]
class Page:
    def goto(self,url,**k): visited.append(url)
class Ctx:
    pages=[Page()]
    def close(self): pass
class PW:
    class chromium:
        @staticmethod
        def launch_persistent_context(**k): return Ctx()
    def __enter__(self): return self
    def __exit__(self,*a): pass
import main
main.sync_playwright=lambda: PW()
tmp=Path("/tmp/ig_queue_test"); shutil.rmtree(tmp,ignore_errors=True); tmp.mkdir()
main.PROGRESS_FILE=tmp/"progress.json"; main.BROWSER_PROFILE=tmp/"bp"

def run(answers):
    it=iter(answers); visited.clear()
    with mock.patch.object(builtins,"input",lambda *_: next(it)):
        main.main()

# Run 1: y, s, y, y, q
run(["y","s","y","y","q"])
p=json.load(open(main.PROGRESS_FILE)); print("run1 completed",len(p["completed"]),"daily",p["daily"],"visited",len(visited))
assert len(p["completed"])==3
# Run 2: all y -> should stop at 10 total today
run(["y"]*20)
p=json.load(open(main.PROGRESS_FILE)); print("run2 completed",len(p["completed"]),"daily",p["daily"],"visited",len(visited))
assert p["daily"][date.today().isoformat()]==10 and len(p["completed"])==10
# Run 3: limit reached -> opens nothing
run([]); print("run3 visited",len(visited)); assert len(visited)==0
# Skipped user stays in queue
assert "dora_dhanu_18" in p["completed"]
print("ALL TESTS PASSED")
