"""CLI (run from tools/dataset-collector): python3 -m collector.collect <source_id> [--sources PATH] [--data-dir PATH] [--max-pages N]"""

import argparse
import json

from .run import collect


def main():
    parser = argparse.ArgumentParser(description="Collect training data from one source.")
    parser.add_argument("source_id")
    parser.add_argument("--sources", default="config/sources.yaml")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--max-pages", type=int, default=None)
    args = parser.parse_args()
    counts = collect(
        args.source_id,
        sources_path=args.sources,
        data_dir=args.data_dir,
        max_pages=args.max_pages,
    )
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
