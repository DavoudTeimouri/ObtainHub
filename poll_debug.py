import json
import os
import time
import urllib.request

API = "https://api.github.com/repos/DavoudTeimouri/ObtainHub"
OUT = "/workspace/project/github/public-repository/ObtainHub/ci_debug.txt"
TARGET = "bb0f040"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"Accept": "application/vnd.github+json"}
if TOKEN:
    HEADERS["Authorization"] = "Bearer " + TOKEN

lines = []
deadline = time.time() + 900
done = False
while time.time() < deadline:
    lines = []
    pending = 0
    for wf in ("release.yml", "build.yml"):
        req = urllib.request.Request(
            API + "/actions/workflows/" + wf + "/runs?per_page=8", headers=HEADERS
        )
        data = json.load(urllib.request.urlopen(req, timeout=30))
        run = next(
            (r for r in data.get("workflow_runs", []) if r["head_sha"].startswith(TARGET)), None
        )
        if run is None:
            lines.append("%s: no run yet" % wf)
            pending += 1
            continue
        finished = run["status"] == "completed"
        pending += 0 if finished else 1
        lines.append(
            "%s: %s/%s  %s" % (wf, run["status"], run["conclusion"], run["html_url"])
        )
        if finished and run["conclusion"] != "success":
            jreq = urllib.request.Request(
                API + "/actions/runs/%d/jobs" % run["id"], headers=HEADERS
            )
            jd = json.load(urllib.request.urlopen(jreq, timeout=30))
            for j in jd.get("jobs", []):
                if j["conclusion"] == "success":
                    continue
                lines.append("  JOB %s [%s]" % (j["name"], j["conclusion"]))
                for s in j.get("steps", []):
                    if s["conclusion"] not in ("success", "skipped", None):
                        lines.append("    STEP: %s -> %s" % (s["name"], s["conclusion"]))
    open(OUT, "w").write("\n".join(lines) + "\n")
    if pending == 0:
        done = True
        break
    time.sleep(25)

print("completed=%s" % done)