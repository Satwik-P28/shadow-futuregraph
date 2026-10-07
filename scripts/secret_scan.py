"""Fail if tracked files look like they contain credentials."""

from __future__ import annotations

import re
import subprocess
import sys

PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"duffel_live_[A-Za-z0-9]+"),
    re.compile(r"tvly-[A-Za-z0-9]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"NEBIUS_API_KEY\s*=\s*\S+"),
    re.compile(r"TAVILY_API_KEY\s*=\s*\S+"),
    re.compile(r"DUFFEL_ACCESS_TOKEN\s*=\s*\S+"),
    re.compile(r"GOOGLE_CLIENT_SECRET\s*=\s*\S+"),
]

ALLOW = {".env.example", "scripts/secret_scan.py", "docs/SECURITY.md"}


def main() -> int:
    listed = subprocess.check_output(["git", "ls-files"], text=True).splitlines()
    failures = []
    for path in listed:
        if path in ALLOW or path.endswith((".png", ".gif", ".jpg")):
            continue
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for pattern in PATTERNS:
            if pattern.search(text):
                failures.append(f"{path}: matched {pattern.pattern}")
    if failures:
        print("\n".join(failures))
        return 1
    print(f"secret scan clean ({len(listed)} tracked files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
