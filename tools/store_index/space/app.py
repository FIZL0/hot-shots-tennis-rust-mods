"""The store index's webhook Space (opentennis M116): a Hugging Face webhook on the store dataset (repo updates,
pull requests) posts here; index.json is rebuilt (build.py) once the posts stop for QUIET seconds, so a burst (an
upload's commit, its PR opening, a maintainer merging several) is one rebuild and at most one commit: the Hub caps
commits per repo. Posts that come during a rebuild make one more after it.

Secrets: HF_TOKEN (writes the dataset), WEBHOOK_SECRET (the webhook's secret, sent as X-Webhook-Secret).
"""

import hmac
import os
import threading
import traceback

from fastapi import FastAPI, Header, HTTPException

import build

app = FastAPI()
state = {"last": "not run yet"}
wake = threading.Event()
QUIET = 30


def worker():
    while True:
        wake.wait()
        wake.clear()
        while wake.wait(QUIET):
            wake.clear()
        try:
            state["last"] = build.run()
        except Exception:
            state["last"] = traceback.format_exc(limit=3)
        print(state["last"], flush=True)


threading.Thread(target=worker, daemon=True).start()
# a Space that slept missed its posts: rebuild on start
wake.set()


@app.post("/webhook")
async def webhook(x_webhook_secret: str = Header("")):
    if not hmac.compare_digest(x_webhook_secret, os.environ.get("WEBHOOK_SECRET", "")) or not x_webhook_secret:
        raise HTTPException(403)
    wake.set()
    return {"ok": True}


@app.get("/")
async def status():
    return {"store": build.REPO, "last": state["last"]}
