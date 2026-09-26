#!/usr/bin/env python3
"""Native MCP headers helper for the official Meta Ads MCP; stdout is a credential channel, never a log.

Usage: auth_headers.py [TOKEN_FILE]
TOKEN_FILE defaults to ~/.config/super-computer-ai/credentials/meta-ads/system-user-token.txt. The path is an
argument, not an environment variable: Claude Code removes credential-like variables (e.g. *TOKEN*) from helpers of
project- and local-scope servers. The file must be a regular file that only its owner can read or write (0600).
"""

import json
import stat
import sys
from pathlib import Path

DEFAULT = Path("~/.config/super-computer-ai/credentials/meta-ads/system-user-token.txt")


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT).expanduser()
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError()
        if info.st_mode & 0o077:
            print("Meta credential file must be readable only by its owner (chmod 600)", file=sys.stderr)
            return 1
        token = path.read_text().strip()
        if not token.startswith("EA") or len(token) < 80 or not token.isascii() or not token.isalnum():
            raise ValueError()
    except (OSError, UnicodeError, ValueError):
        print("Meta credential file missing or invalid", file=sys.stderr)
        return 1
    print(json.dumps({"Authorization": "Bearer " + token}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
