
from __future__ import annotations

import argparse
import json

from .macro_model_library import evaluate


def main():
    parser = argparse.ArgumentParser(
        description="V3.24 Macro Model Library / Business Cycle Core"
    )
    parser.add_argument(
        "--config",
        default="config/macro_model_library.toml",
    )
    parser.add_argument(
        "--as-of",
        default=None,
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
    )
    args = parser.parse_args()

    result = evaluate(
        config_path=args.config,
        as_of=args.as_of,
        force_refresh=args.refresh,
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
