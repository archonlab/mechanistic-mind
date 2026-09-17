"""MM-SUBSTRATE-1 InternalMaterialMedium — preregistered structural params."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any


# Footprint order matches PhysicalBodyConfig BODY-2 defaults
FOOTPRINT: tuple[tuple[int, int], ...] = ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1))
# Undirected edges: center (0) to each arm
EDGES: tuple[tuple[int, int], ...] = ((0, 1), (0, 2), (0, 3), (0, 4))


@dataclass
class InternalMediumConfig:
    n_sites: int = 5
    n_species: int = 3
    D: float = 0.08
    gamma: float = 0.01
    kappa_s: float = 0.01
    kappa_c: float = 0.008
    C_max: float = 2.0
    c0: float = 0.15
    # research / opt-in cuts
    medium_enabled: bool = True
    coupling_enabled: bool = True
    diffusion_enabled: bool = True
    dissipation_enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_internal_medium_config() -> InternalMediumConfig:
    return InternalMediumConfig()


def adjacency() -> list[list[int]]:
    adj = [[] for _ in range(5)]
    for a, b in EDGES:
        adj[a].append(b)
        adj[b].append(a)
    return adj
