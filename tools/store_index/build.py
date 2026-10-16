"""Builds the mod store's index.json (opentennis M116) and commits it to the store's main when it changed.

The store is the Hugging Face dataset FIZL0/opentennis-mods: merged mods under mods/<id>/ on main, each upload an
open pull request. Listing it took the game a tree and every meta.json per PR (86 API calls with 82 open PRs, past
HF's 500 per 5 minutes per IP after a few listings). The game now reads index.json (one file on main) and the open PR
list, and reads only PRs the index doesn't have yet.

index.json:
  {"version": 1, "built": <unix s>,
   "pulls": {"<n>": {"author": <PR author>, "commit": <PR head>}},   every PR open at build time
   "entries": [{"meta": <meta.json>, "rev": "main" | "refs/pr/<n>", "verified": <on main>, "oid": <folder tree id>}]}
main's mods first, then each PR's, newest first, not merged (the game merges and re-checks every meta).

A rebuild reuses the last index: a PR whose head commit is the same isn't read again, and a main folder whose tree
id is the same keeps its meta. So a rebuild with nothing new costs ~4 API calls.

Runs from the webhook Space (space/app.py, on every store change) and hourly from .github/workflows/store-index.yml.
HF_TOKEN: a token that can write the dataset. `python build.py --dry-run` prints it instead of committing.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

from huggingface_hub import HfApi
from huggingface_hub.errors import HfHubHTTPError

REPO = "FIZL0/opentennis-mods"
HF = "https://huggingface.co"
VERSION = 1
PATH = "index.json"


def fetch(url, token):
    """GET url: its bytes, or None on 404."""
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"} if token else {})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def resolve(rev, path):
    return f"{HF}/datasets/{REPO}/resolve/{rev.replace('/', '%2F')}/{path}"


def folders(api, rev):
    """mods/<id> folders at rev: {id: tree id}; none when mods/ isn't there."""
    try:
        return {f.path[len("mods/"):]: f.tree_id for f in api.list_repo_tree(REPO, "mods", revision=rev, repo_type="dataset") if hasattr(f, "tree_id")}
    except HfHubHTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return {}
        raise


def meta(rev, id, token):
    """mods/<id>/meta.json at rev, if it's JSON for this id (the game checks the rest)."""
    b = fetch(resolve(rev, f"mods/{id}/meta.json"), token)
    try:
        m = json.loads(b) if b else None
    except ValueError:
        return None
    return m if isinstance(m, dict) and m.get("id") == id else None


def entries(api, rev, token, author=None, keep=()):
    """rev's mods as index entries; `keep`: last index's entries at rev, reused where the folder is unchanged."""
    old = {(e["meta"]["id"], e.get("oid")): e for e in keep}
    out = []
    for id, oid in sorted(folders(api, rev).items()):
        e = old.get((id, oid))
        if e is None:
            m = meta(rev, id, token)
            if m is None:
                continue
            e = {"meta": m, "rev": rev, "verified": rev == "main", "oid": oid}
        if author is not None:
            e["meta"]["author"] = author
        out.append(e)
    return out


def last(token):
    """The index on main now, or None."""
    b = fetch(resolve("main", PATH), token)
    try:
        ix = json.loads(b) if b else None
    except ValueError:
        return None
    return ix if isinstance(ix, dict) and ix.get("version") == VERSION else None


def build(api, token, old):
    refs = api.list_repo_refs(REPO, repo_type="dataset", include_pull_requests=True)
    heads = {r.ref: r.target_commit for r in refs.pull_requests or []}
    prs = api.get_repo_discussions(REPO, repo_type="dataset", discussion_type="pull_request", discussion_status="open")
    open_ = sorted(((d.num, d.author or "") for d in prs if d.is_pull_request and d.status == "open"), reverse=True)
    old_entries = (old or {}).get("entries", [])
    old_pulls = (old or {}).get("pulls", {})
    at = lambda rev: [e for e in old_entries if e.get("rev") == rev]
    out = entries(api, "main", token, keep=at("main"))
    pulls = {}
    for n, who in open_:
        rev = f"refs/pr/{n}"
        commit = heads.get(rev, "")
        was = old_pulls.get(str(n))
        if was and was.get("commit") == commit and was.get("author") == who and commit:
            out += at(rev)
        else:
            out += entries(api, rev, token, author=who)
        pulls[str(n)] = {"author": who, "commit": commit}
    return {"version": VERSION, "built": int(time.time()), "pulls": pulls, "entries": out}


def same(a, b):
    body = lambda ix: json.dumps({"pulls": ix.get("pulls"), "entries": ix.get("entries")}, sort_keys=True)
    return a is not None and body(a) == body(b)


def run(dry=False):
    """Rebuilds the index; commits it only if it changed. Returns what it did."""
    token = os.environ.get("HF_TOKEN") or None
    api = HfApi(token=token)
    old = last(token)
    ix = build(api, token, old)
    said = f"{len(ix['entries'])} mods, {len(ix['pulls'])} open PRs"
    if dry:
        json.dump(ix, sys.stdout, indent=1)
        return said + " (dry run)"
    if same(old, ix):
        return said + ": unchanged"
    data = json.dumps(ix, separators=(",", ":"), sort_keys=True).encode()
    api.upload_file(path_or_fileobj=data, path_in_repo=PATH, repo_id=REPO, repo_type="dataset", commit_message=f"Store index: {said}")
    return said + ": committed"


if __name__ == "__main__":
    print(run("--dry-run" in sys.argv[1:]), file=sys.stderr)
