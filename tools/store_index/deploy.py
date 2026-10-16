"""Sets up the store index's webhook Space (opentennis M116), once, as the dataset's owner.

  HF_TOKEN=<write token for FIZL0/opentennis-mods> python tools/store_index/deploy.py

Creates (or updates) the Docker Space FIZL0/opentennis-mods-index from space/ + build.py, gives it the secrets
HF_TOKEN and a fresh WEBHOOK_SECRET, and points a webhook on the dataset (repo updates and PR/discussion events) at
its /webhook. Rerun it after changing build.py or space/ (the webhook is replaced, so its secret stays in step).
The hourly GitHub Action (.github/workflows/store-index.yml) needs the same token: `gh secret set HF_TOKEN`.
"""

import os
import secrets
import sys
from pathlib import Path

from huggingface_hub import CommitOperationAdd, HfApi

import build

SPACE = "FIZL0/opentennis-mods-index"
HERE = Path(__file__).parent


def main():
    token = os.environ["HF_TOKEN"]
    api = HfApi(token=token)
    api.create_repo(SPACE, repo_type="space", space_sdk="docker", exist_ok=True)
    files = [HERE / "build.py", *sorted((HERE / "space").iterdir())]
    ops = [CommitOperationAdd(path_in_repo=f.name, path_or_fileobj=str(f)) for f in files if f.is_file()]
    api.create_commit(SPACE, ops, repo_type="space", commit_message="Store index Space")
    secret = secrets.token_urlsafe(32)
    api.add_space_secret(SPACE, "HF_TOKEN", token)
    api.add_space_secret(SPACE, "WEBHOOK_SECRET", secret)
    url = f"https://{SPACE.replace('/', '-').replace('_', '-').lower()}.hf.space/webhook"
    for w in api.list_webhooks():
        if w.url == url:
            api.delete_webhook(w.id)
    api.create_webhook(url=url, watched=[{"type": "dataset", "name": build.REPO}], domains=["repo", "discussion"], secret=secret)
    print(f"Space {SPACE} up, webhook -> {url}", file=sys.stderr)


if __name__ == "__main__":
    main()
