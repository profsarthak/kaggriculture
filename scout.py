"""Scour public repositories for approaches we have not tried.

We are at a local optimum for our architecture: an automated search finds
nothing, nine structural ideas have been rejected, and our win rate against
matched opponents sits at 49%. That is not a tuning problem, it is an
architecture ceiling -- our agent is greedy, ranking jobs and sending the
nearest worker, with no planning or sequencing.

Other competitors have published. This collects what is public, records what is
new since the last run, and pulls the parts most likely to contain an approach
rather than boilerplate.

On the rules: the prohibition is on *privately* sharing code, and external tools
are permitted when "reasonably accessible to all". Public repositories qualify.
The intent here is to read for approach, not to lift strategy code -- both on
principle and because winner obligations would require open-sourcing whatever we
submit.

Run:  python scout.py            # refresh and show what changed
      python scout.py --fetch    # also download READMEs for anything new
"""

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
SEEN = os.path.join(DATA, "scout-seen.json")
NOTES = os.path.join(DATA, "scout-notes")

QUERIES = [
    "kaggriculture",
    "kaggle kaggriculture agent",
]

# Files most likely to describe an approach rather than repeat the rules.
INTERESTING = ("README.md", "readme.md", "STRATEGY.md", "NOTES.md", "AGENTS.md")


def gh(*args):
    try:
        proc = subprocess.run(
            ["gh", *args], capture_output=True, encoding="utf-8",
            errors="replace", timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout if proc.returncode == 0 else None


def search():
    found = {}
    for query in QUERIES:
        out = gh("search", "repos", *query.split(), "--limit", "60",
                 "--json", "fullName,description,updatedAt,stargazersCount")
        if not out:
            continue
        try:
            for repo in json.loads(out):
                found[repo["fullName"]] = repo
        except json.JSONDecodeError:
            continue
    return found


def load_seen():
    if not os.path.exists(SEEN):
        return {}
    try:
        with open(SEEN, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_seen(seen):
    os.makedirs(DATA, exist_ok=True)
    with open(SEEN, "w", encoding="utf-8") as f:
        json.dump(seen, f, indent=1, sort_keys=True)


def fetch_notes(full_name):
    """Pull whichever descriptive file the repo actually has."""
    os.makedirs(NOTES, exist_ok=True)
    safe = full_name.replace("/", "__")
    for name in INTERESTING:
        out = gh("api", f"repos/{full_name}/contents/{name}",
                 "--jq", ".content")
        if not out or not out.strip():
            continue
        import base64
        try:
            text = base64.b64decode(out.strip()).decode("utf-8", "replace")
        except (ValueError, UnicodeDecodeError):
            continue
        path = os.path.join(NOTES, f"{safe}.{name}")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path, len(text)
    return None, 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true",
                    help="download descriptive files for repos not seen before")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"=== scout {stamp} ===\n")

    repos = search()
    if not repos:
        print("  no results -- is the gh CLI authenticated?")
        return

    seen = load_seen()
    new = {k: v for k, v in repos.items() if k not in seen}
    updated = {
        k: v for k, v in repos.items()
        if k in seen and v.get("updatedAt") != seen[k].get("updatedAt")
    }

    print(f"{len(repos)} public repos; {len(new)} new, {len(updated)} updated since last run\n")

    def show(label, group):
        if not group:
            return
        print(f"--- {label} ---")
        for name, repo in sorted(group.items(), key=lambda kv: -kv[1].get("stargazersCount", 0)):
            stars = repo.get("stargazersCount", 0)
            desc = (repo.get("description") or "")[:70]
            print(f"  {name:<42} {stars:>3}* {desc}")
        print()

    show("NEW", new)
    show("UPDATED", updated)

    if args.fetch and (new or updated):
        print("--- fetching descriptions ---")
        for name in list(new) + list(updated):
            path, size = fetch_notes(name)
            if path:
                print(f"  {name:<42} {size:>6,} chars -> {os.path.basename(path)}")

    save_seen(repos)
    print(f"\n  state saved to {SEEN}")
    print("  Read for approach, not to copy strategy code.")


if __name__ == "__main__":
    main()
