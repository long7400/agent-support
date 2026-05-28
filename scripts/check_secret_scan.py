import json
import subprocess
import sys


def main() -> int:
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        check=True,
        capture_output=True,
    )
    files = [path for path in listed.stdout.decode().split("\0") if path]

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
