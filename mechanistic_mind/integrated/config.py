from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class IntegratedConfig:
    """Pre-run causal cuts. False means the contribution is genuinely absent."""

    predictive_compression: bool = True
    multiscale_prediction: bool = True
    prospective_composition: bool = True
    instrumental_observation: bool = True
    bounded_memory: bool = True
    retrieval: bool = True
    causal_trace_capacity: int = 512
    prospective_depth: int = 3

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

