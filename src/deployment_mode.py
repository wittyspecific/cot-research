from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


LOCAL = "LOCAL"
REMOTE_GATEWAY = "REMOTE_GATEWAY"


@dataclass(frozen=True)
class DeploymentConfig:
    mode: str = LOCAL

    @property
    def is_remote(self) -> bool:
        return self.mode == REMOTE_GATEWAY

    @property
    def is_local(self) -> bool:
        return self.mode == LOCAL


def deployment_config_from_mapping(mapping: Mapping[str, Any] | None) -> DeploymentConfig:
    raw = dict(mapping or {})
    mode = str(raw.get("mode", LOCAL) or LOCAL).strip().upper()
    aliases = {
        "REMOTE": REMOTE_GATEWAY,
        "GATEWAY": REMOTE_GATEWAY,
        "REMOTE_GATEWAY": REMOTE_GATEWAY,
        "LOCAL": LOCAL,
    }
    normalized = aliases.get(mode)
    if normalized is None:
        raise ValueError("[deployment] mode muss LOCAL oder REMOTE_GATEWAY sein.")
    return DeploymentConfig(mode=normalized)
