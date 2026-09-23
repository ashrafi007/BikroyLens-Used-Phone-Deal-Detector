"""
Trigger service for the daily scrape -> load -> normalize -> retrain cycle.

Exists as its own free Render Web Service (not bolted onto bikroylens-api)
specifically so the heavy scraping/ML dependencies (Scrapy, pandas,
xgboost, scikit-learn) don't bloat the actual live API's build and
cold-start time. Render's paid Cron Job product would've been a cleaner
fit for "run this once a day," but requires a paid plan -- this reuses
what a free Web Service can already do (run arbitrary code in response
to an HTTP request) to get the same outcome at zero cost, triggered by
a GitHub Actions scheduled workflow that just calls POST /run.

Free Render Web Services sleep after ~15 minutes with no incoming HTTP
traffic and wake back up on the next request -- the pipeline can take
longer than that to finish, so the triggering workflow is expected to
poll GET /status periodically during the run, which also happens to
generate the traffic that keeps this service awake until it's done.
"""

import asyncio
import os
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="BikroyLens Pipeline Trigger")

TRIGGER_SECRET = os.environ.get("PIPELINE_TRIGGER_SECRET")
MAX_LOG_LINES = 200

state = {
    "status": "idle",  # idle | running | done | failed
    "started_at": None,
    "finished_at": None,
    "returncode": None,
    "log_tail": [],
}


async def _run_pipeline():
    state["status"] = "running"
    state["started_at"] = datetime.now(timezone.utc).isoformat()
    state["finished_at"] = None
    state["returncode"] = None
    state["log_tail"] = []

    process = await asyncio.create_subprocess_exec(
        "bash",
        "scripts/cloud_pipeline.sh",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    async for line in process.stdout:
        text = line.decode(errors="replace").rstrip()
        print(text, flush=True)  # also shows up in Render's own Logs tab
        state["log_tail"].append(text)
        if len(state["log_tail"]) > MAX_LOG_LINES:
            state["log_tail"] = state["log_tail"][-MAX_LOG_LINES:]

    returncode = await process.wait()
    state["status"] = "done" if returncode == 0 else "failed"
    state["returncode"] = returncode
    state["finished_at"] = datetime.now(timezone.utc).isoformat()


@app.get("/")
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/status")
async def status():
    return state


@app.post("/run")
async def run(x_trigger_secret: str = Header(default="")):
    if not TRIGGER_SECRET:
        raise HTTPException(500, "PIPELINE_TRIGGER_SECRET not configured on the server")
    if x_trigger_secret != TRIGGER_SECRET:
        raise HTTPException(403, "invalid trigger secret")
    if state["status"] == "running":
        return JSONResponse({"status": "already running", **state}, status_code=409)

    asyncio.create_task(_run_pipeline())
    return {"status": "started"}
