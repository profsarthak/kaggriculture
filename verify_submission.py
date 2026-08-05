"""Pre-flight check: run the built artefact the way Kaggle will run it.

Kaggle reads the agent file and exec's it from an unrelated working directory,
so this extracts the tarball to a scratch dir, chdir's somewhere else, and runs
a full episode against `starter` plus a self-play episode (which is exactly what
the platform's validation episode does).

Catches: undefined `__file__`, unresolvable imports, per-turn timeouts, and
anything that only shows up outside the repo.

Run:  python verify_submission.py
"""

import os
import shutil
import statistics
import tarfile
import tempfile
import time

from kaggle_environments import make

HERE = os.path.dirname(os.path.abspath(__file__))
TAR = os.path.join(HERE, "submission.tar.gz")
ACT_TIMEOUT_MS = 1000          # kaggriculture.json: actTimeout = 1 second


def main():
    if not os.path.exists(TAR):
        raise SystemExit("no submission.tar.gz -- run `python build.py` first")

    work = tempfile.mkdtemp(prefix="kaggri_sub_")
    with tarfile.open(TAR) as tar:
        names = tar.getnames()
        tar.extractall(work)
    print(f"tarball contents: {names}")

    entry = os.path.join(work, "main.py")
    if not os.path.exists(entry):
        raise SystemExit("main.py is not at the root of the tarball")

    original = os.getcwd()
    outside = os.path.expanduser("~")
    failures = []
    try:
        os.chdir(outside)
        print(f"running from {outside} (deliberately not the repo)\n")

        for label, opponent in (("vs starter", "starter"), ("validation self-play", entry)):
            t0 = time.perf_counter()
            env = make("kaggriculture", configuration={"seed": 11}, debug=True)
            env.run([entry, opponent])
            final = env.steps[-1]
            elapsed = time.perf_counter() - t0
            per_turn = elapsed / max(1, len(env.steps)) * 1000

            statuses = [s.status for s in final]
            rewards = [s.reward for s in final]
            ok = all(s == "DONE" for s in statuses)
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}: "
                  f"status={statuses} reward={rewards}")
            print(f"         {elapsed:.1f}s total, ~{per_turn:.1f} ms/turn "
                  f"(both agents; limit {ACT_TIMEOUT_MS} ms/turn each)")
            if not ok:
                failures.append(label)
    finally:
        os.chdir(original)
        shutil.rmtree(work, ignore_errors=True)

    if failures:
        print(f"\nFAILED: {failures} -- do not submit")
        return 1
    print("\nall checks passed -- safe to submit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
