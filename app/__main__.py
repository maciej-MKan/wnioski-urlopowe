"""CLI narzędzi administracyjnych: `python -m app <komenda>` (§23.3)."""
from __future__ import annotations

import argparse
import sys
from typing import Optional

from .admin import reset_password


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app", description="Narzędzia administracyjne")
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("reset-haslo", help="Reset hasła konta (§23.3)")
    r.add_argument("username")
    r.add_argument("password", nargs="?", help="nowe hasło; pominięte → wygenerowane i wypisane")
    args = parser.parse_args(argv)

    if args.cmd == "reset-haslo":
        ok, msg = reset_password(args.username, args.password)
        print(msg, file=sys.stdout if ok else sys.stderr)
        return 0 if ok else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
