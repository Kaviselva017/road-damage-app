from __future__ import annotations

import subprocess
import sys
from pathlib import PurePosixPath


BLOCKED_EXACT = {
    "backend/.env",
    "backend/cert.pem",
    "backend/key.pem",
    "backend/road_damage.db",
    "road_damage.db",
    "roadwatch.env",
}

BLOCKED_PREFIXES = (
    ".venv/",
    ".venv_clean/",
    "backend/uploads/",
    "uploads/",
    "dashboard/node_modules/",
    "dashboard/dist/",
    "static/",
)


def tracked_files() -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [path for path in proc.stdout.decode("utf-8", errors="replace").split("\0") if path]


def find_blocked(paths: list[str]) -> list[str]:
    blocked: list[str] = []
    for raw_path in paths:
        path = PurePosixPath(raw_path).as_posix()
        if path in BLOCKED_EXACT or any(path.startswith(prefix) for prefix in BLOCKED_PREFIXES):
            blocked.append(path)
    return sorted(blocked)


def main() -> int:
    try:
        tracked = tracked_files()
    except subprocess.CalledProcessError as exc:
        print("Failed to list tracked files with git.", file=sys.stderr)
        return exc.returncode or 1

    blocked = find_blocked(tracked)
    if not blocked:
        print("Repository hygiene check passed.")
        return 0

    print("Blocked tracked files detected:", file=sys.stderr)
    for path in blocked:
        print(f" - {path}", file=sys.stderr)
    print(
        "Remove them from git tracking and keep them ignored before merging.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
