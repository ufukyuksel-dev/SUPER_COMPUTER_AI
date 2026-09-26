"""CLI: uv run jev "goal" --url https://... [--text ...] [--expect ...]"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from jev import env, runlog
from jev.brain import Brain, run
from jev.browser import Browser


def main() -> None:
    ap = argparse.ArgumentParser(prog="jev", description="Jev picks, Chrome clicks.")
    ap.add_argument("goal")
    ap.add_argument("--url", required=True, help="start page")
    ap.add_argument("--text", help="text to type into a search field (used once)")
    ap.add_argument("--max-steps", type=int, default=10)
    ap.add_argument("--profile", default="cli")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--expect", help="URL/title substring of the real destination (for the run log)")
    ap.add_argument("--keep-open", action="store_true", help="leave Chrome open until Enter is pressed")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(asctime)s %(name)s %(message)s")
    env.load()
    asyncio.run(_main(args))


async def _main(args: argparse.Namespace) -> None:
    browser = Browser(profile=args.profile, headless=args.headless)
    try:
        await browser.open(args.url)
        result = await run(browser, Brain(), args.goal, text=args.text, max_steps=args.max_steps)
        rec = runlog.record(args.goal, result, args.expect)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("run log:", json.dumps(rec, ensure_ascii=False))
        if args.keep_open:
            await asyncio.to_thread(input, "Press Enter to close Chrome… ")
    finally:
        await browser.close()


if __name__ == "__main__":
    main()
