import json
import subprocess
import sys
from pathlib import PurePath

GENERATED_DIR_NAMES = {"node_modules"}


def should_scan(path: str) -> bool:
    return not any(part in GENERATED_DIR_NAMES for part in PurePath(path).parts)


def main() -> int:
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        check=True,
        capture_output=True,
    )
    files = [path for path in listed.stdout.decode().split("\0") if path and should_scan(path)]

    if not files:
        print("No files to scan.")
        return 0

    scanned = subprocess.run(
        [sys.executable, "-m", "detect_secrets", "scan", *files],
        check=False,
        capture_output=True,
        text=True,
    )
    if scanned.returncode != 0:
        sys.stderr.write(scanned.stderr)
        return scanned.returncode

    report = json.loads(scanned.stdout)
    results = report.get("results", {})
    if results:
        print(json.dumps(results, indent=2, sort_keys=True), file=sys.stderr)
        print("Secret scan found potential secrets.", file=sys.stderr)
        return 1

    print("Secret scan passed: no findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
