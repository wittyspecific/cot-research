from __future__ import annotations

from typing import Any


def find_strategy_logic_blocks(snapshot: Any) -> list[tuple[str, dict]]:
    """Find immutable strategy_logic blocks without assuming one snapshot shape."""
    found: list[tuple[str, dict]] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            block = value.get("strategy_logic")
            if isinstance(block, dict):
                found.append((path or "snapshot", block))
            for key, child in value.items():
                if key == "strategy_logic":
                    continue
                child_path = f"{path}.{key}" if path else str(key)
                walk(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                child_path = f"{path}[{index}]" if path else f"[{index}]"
                walk(child, child_path)

    walk(snapshot, "")
    return found
