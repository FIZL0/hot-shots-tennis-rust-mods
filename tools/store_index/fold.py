"""Folds one uploader's open pull requests on the mod store into one (opentennis: the Hub caps commits per repo, and
a mod per PR made any pass over the store, a card backfill or a fix, a commit per mod).

  HF_TOKEN=<the uploader's token> python fold.py <uploader> [--go]

Each open PR by <uploader>: its own mods are the mods/<id>/ folders that differ from main (a PR's tree is main as it
was plus the upload). The newest PR's copy of an id wins. One commit to main with create_pr opens a single PR holding
all of them: LFS files are copied from their PR server side (no re-upload), small files fetched and re-added. Then the
old PRs are closed (no commits). Without --go it prints what it would do. The game sends the uploader's later uploads
onto their newest open PR, so it stays one PR.
"""

import sys
import time

from huggingface_hub.errors import EntryNotFoundError
from huggingface_hub import CommitOperationAdd, CommitOperationCopy, HfApi, hf_hub_download

from build import REPO


def tree(api, rev):
    """mods/ at rev: {id: (folder tree id, [files])}."""
    out = {}
    try:
        got = list(api.list_repo_tree(REPO, "mods", revision=rev, repo_type="dataset", recursive=True))
    except EntryNotFoundError:
        return out
    for f in got:
        parts = f.path.split("/")
        if len(parts) == 2 and hasattr(f, "tree_id"):
            out.setdefault(parts[1], [None, []])[0] = f.tree_id
        elif len(parts) > 2 and not hasattr(f, "tree_id"):
            out.setdefault(parts[1], [None, []])[1].append(f)
    return out


def main():
    who, go = sys.argv[1], "--go" in sys.argv
    api = HfApi()
    prs = sorted(d.num for d in api.get_repo_discussions(REPO, repo_type="dataset", author=who, discussion_type="pull_request", discussion_status="open"))
    print(f"{len(prs)} open PRs by {who}")
    main_ = {id: t for id, (t, _) in tree(api, "main").items()}
    pick = {}  # id -> (pr, files); newest PR last, so it wins
    for n in prs:
        for id, (t, files) in tree(api, f"refs/pr/{n}").items():
            if main_.get(id) != t:
                pick[id] = (n, files)
        time.sleep(0.3)  # HF: 500 API calls per 5 minutes
    print(f"{len(pick)} mods: " + ", ".join(f"{id}@{n}" for id, (n, _) in sorted(pick.items())))
    empty = [n for n in prs if all(p != n for p, _ in pick.values())]
    if empty:
        print(f"PRs with nothing newer than main or a later PR: {empty}")
    if not go:
        return print("dry run: rerun with --go")
    ops = []
    for id, (n, files) in sorted(pick.items()):
        for f in files:
            if f.lfs:
                ops.append(CommitOperationCopy(src_path_in_repo=f.path, path_in_repo=f.path, src_revision=f"refs/pr/{n}"))
            else:
                p = hf_hub_download(REPO, f.path, repo_type="dataset", revision=f"refs/pr/{n}")
                ops.append(CommitOperationAdd(path_in_repo=f.path, path_or_fileobj=p))
    c = api.create_commit(REPO, ops, repo_type="dataset", create_pr=True, commit_message=f"Upload {len(pick)} mods ({who}'s uploads in one PR)",
                          commit_description=f"Folds {who}'s open PRs {', '.join(f'#{n}' for n in prs)} into one.")
    print("opened", c.pr_url)
    for n in prs:
        api.change_discussion_status(REPO, n, "closed", repo_type="dataset", comment=f"Folded into {c.pr_url}")
        time.sleep(0.3)
    print(f"closed {len(prs)} PRs")


if __name__ == "__main__":
    main()
