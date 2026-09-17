"""MM canonical model identity and manifests."""

from .identity import (
    MODEL_CODENAME,
    MODEL_FAMILY,
    MODEL_VERSION,
    RUNTIME_VERSION,
    display_name,
    promotion_class,
)
from .tiktaalik import (
    build_manifest,
    experimental_overrides,
    is_canonical_tiktaalik,
    tiktaalik_config,
)

__all__ = [
    "MODEL_CODENAME",
    "MODEL_FAMILY",
    "MODEL_VERSION",
    "RUNTIME_VERSION",
    "build_manifest",
    "display_name",
    "experimental_overrides",
    "is_canonical_tiktaalik",
    "promotion_class",
    "tiktaalik_config",
]
