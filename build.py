"""Build a self-contained submission from the dev sources.

Why not just tar main.py + farmlib.py: kaggle-environments loads an agent by
reading the file and exec'ing it, so `__file__` is undefined inside a
submission. The usual "add my own directory to sys.path" trick raises NameError
and fails the validation episode. Rather than guess which directory the sandbox
puts on sys.path, we emit one file with no imports to resolve.

farmlib.py stays the source of truth for development and for Phase C's strategy
portfolio; this just flattens it.

Run:  python build.py            # writes dist/main.py and submission.tar.gz
"""

import os
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "dist")

ENTRY = '''

# --- submission entry point (appended by build.py) ------------------------
_agent = make_agent(Config())


def agent(obs):
    return _agent(obs)
'''


def build(config_kwargs=None, name="main.py"):
    with open(os.path.join(HERE, "farmlib.py"), encoding="utf-8") as f:
        source = f.read()

    entry = ENTRY
    if config_kwargs:
        args = ", ".join(f"{k}={v!r}" for k, v in config_kwargs.items())
        entry = entry.replace("make_agent(Config())", f"make_agent(Config({args}))")

    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, name)
    with open(out, "w", encoding="utf-8") as f:
        f.write(source + entry)
    return out


def parse_overrides(spec):
    kwargs = {}
    for pair in (spec or "").split(","):
        key, _, value = pair.partition("=")
        key, value = key.strip(), value.strip()
        if not key:
            continue
        if value.lower() in ("true", "false"):
            kwargs[key] = value.lower() == "true"
        else:
            try:
                kwargs[key] = float(value) if "." in value else int(value)
            except ValueError:
                kwargs[key] = value
    return kwargs


def main():
    import sys

    # `python build.py melon_tiles=20,pasture_target=1` bakes overrides into the
    # artefact, so an exploration probe can be submitted without editing the
    # defaults that every other tool reads.
    overrides = parse_overrides(sys.argv[1]) if len(sys.argv) > 1 else None
    if overrides:
        print(f"baking overrides: {overrides}")

    out = build(overrides)
    tar_path = os.path.join(HERE, "submission.tar.gz")
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(out, arcname="main.py")

    size = os.path.getsize(tar_path)
    print(f"wrote {out}")
    print(f"wrote {tar_path} ({size:,} bytes)")
    print("\nverify before submitting:")
    print("  python verify_submission.py")


if __name__ == "__main__":
    main()
