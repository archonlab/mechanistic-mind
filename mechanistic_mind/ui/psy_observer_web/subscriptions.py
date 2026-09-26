"""Demand-driven Observer display subscriptions (Observer-only; not cognition).

Scientific evidence / receipts are Tier 0 and are NEVER gated by these products.
Changing subscriptions or detail presets must not mutate organism/runtime science.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

# --- Product IDs (explicit; prefer these over ad-hoc booleans) ---------------

PRODUCT_WORLD = "world"
PRODUCT_TELEMETRY = "telemetry"
PRODUCT_MECHANISMS = "mechanisms"
PRODUCT_COGNITION = "cognition"
PRODUCT_PSC = "psc"
PRODUCT_SMC = "smc"
PRODUCT_HISTORICAL_SENSORIMOTOR = "historical_sensorimotor_selection"
PRODUCT_PREDICTION = "prediction"
PRODUCT_HISTORY = "history"
PRODUCT_COMPRESSION = "compression"
PRODUCT_GRAPHS = "graphs"
PRODUCT_DIAGNOSTICS = "diagnostics"
PRODUCT_GEOMETRY = "geometry"
PRODUCT_SIGNALS = "signals"
PRODUCT_EXPERIMENTER = "experimenter"
PRODUCT_SIGNAL_SENSORIMOTOR = "signal_sensorimotor"

ALL_PRODUCTS: tuple[str, ...] = (
    PRODUCT_WORLD,
    PRODUCT_TELEMETRY,
    PRODUCT_MECHANISMS,
    PRODUCT_COGNITION,
    PRODUCT_PSC,
    PRODUCT_SMC,
    PRODUCT_HISTORICAL_SENSORIMOTOR,
    PRODUCT_PREDICTION,
    PRODUCT_HISTORY,
    PRODUCT_COMPRESSION,
    PRODUCT_GRAPHS,
    PRODUCT_DIAGNOSTICS,
    PRODUCT_GEOMETRY,
    PRODUCT_SIGNALS,
    PRODUCT_EXPERIMENTER,
    PRODUCT_SIGNAL_SENSORIMOTOR,
)

# Suggested display cadences (Hz). Simulation is independent.
DEFAULT_CADENCE_HZ: dict[str, float] = {
    PRODUCT_WORLD: 20.0,
    PRODUCT_TELEMETRY: 4.0,
    PRODUCT_MECHANISMS: 2.0,
    PRODUCT_COGNITION: 3.0,
    PRODUCT_PSC: 3.0,
    PRODUCT_SMC: 2.0,
    PRODUCT_HISTORICAL_SENSORIMOTOR: 2.0,
    PRODUCT_PREDICTION: 2.0,
    PRODUCT_HISTORY: 1.0,
    PRODUCT_COMPRESSION: 1.0,
    PRODUCT_GRAPHS: 1.5,
    PRODUCT_DIAGNOSTICS: 1.0,
    PRODUCT_GEOMETRY: 10.0,
    PRODUCT_SIGNALS: 2.0,
    PRODUCT_EXPERIMENTER: 2.0,
    PRODUCT_SIGNAL_SENSORIMOTOR: 2.0,
}

# Presets are Observer/UI only — never mechanism activation.
PRESET_MINIMAL: frozenset[str] = frozenset({
    PRODUCT_WORLD,
    PRODUCT_TELEMETRY,
    PRODUCT_MECHANISMS,
})
PRESET_NORMAL: frozenset[str] = frozenset({
    PRODUCT_WORLD,
    PRODUCT_TELEMETRY,
    PRODUCT_MECHANISMS,
    PRODUCT_COGNITION,
    PRODUCT_SMC,
    PRODUCT_HISTORICAL_SENSORIMOTOR,
    PRODUCT_GEOMETRY,
    PRODUCT_EXPERIMENTER,
    PRODUCT_SIGNAL_SENSORIMOTOR,
})
PRESET_FULL: frozenset[str] = frozenset(ALL_PRODUCTS)

PRESETS: dict[str, frozenset[str]] = {
    "MINIMAL": PRESET_MINIMAL,
    "NORMAL": PRESET_NORMAL,
    "FULL": PRESET_FULL,
}

# Frame detail string used by existing compact/full path.
PRESET_FRAME_DETAIL: dict[str, str] = {
    "MINIMAL": "compact",
    "NORMAL": "compact",
    "FULL": "full",  # when PAUSED; RUNNING still prefers compact for lock-hold
}


@dataclass
class ObserverInterest:
    """Mutable interest set for optional live Observer products."""

    preset: str = "NORMAL"
    products: set[str] = field(default_factory=lambda: set(PRESET_NORMAL))
    # Per-product last emit monotonic times for cadence gating.
    _last_emit: dict[str, float] = field(default_factory=dict)
    # Producer call counters (debug / tests).
    producer_calls: dict[str, int] = field(default_factory=dict)
    generation: int = 0  # bumps on every interest change (reconnect-safe replace)

    def snapshot(self) -> dict[str, Any]:
        return {
            "preset": self.preset,
            "products": sorted(self.products),
            "cadence_hz": {k: DEFAULT_CADENCE_HZ[k] for k in sorted(self.products) if k in DEFAULT_CADENCE_HZ},
            "generation": int(self.generation),
            "producer_calls": dict(self.producer_calls),
            "note": "Observer display interest only; scientific evidence is not gated.",
        }

    def set_preset(self, name: str) -> dict[str, Any]:
        key = str(name or "NORMAL").upper()
        if key not in PRESETS:
            key = "NORMAL"
        self.preset = key
        self.products = set(PRESETS[key])
        self.generation += 1
        return self.snapshot()

    def set_products(self, products: Iterable[str]) -> dict[str, Any]:
        wanted = {str(p) for p in products if str(p) in ALL_PRODUCTS}
        # Always keep world+telemetry for a usable live Observer.
        wanted |= {PRODUCT_WORLD, PRODUCT_TELEMETRY}
        self.products = wanted
        self.preset = "CUSTOM"
        self.generation += 1
        return self.snapshot()

    def add(self, product: str) -> dict[str, Any]:
        p = str(product)
        if p in ALL_PRODUCTS:
            self.products.add(p)
            self.preset = "CUSTOM"
            self.generation += 1
        return self.snapshot()

    def remove(self, product: str) -> dict[str, Any]:
        p = str(product)
        if p in (PRODUCT_WORLD, PRODUCT_TELEMETRY):
            return self.snapshot()  # cannot remove core live view
        self.products.discard(p)
        self.preset = "CUSTOM"
        self.generation += 1
        return self.snapshot()

    def wants(self, product: str) -> bool:
        return str(product) in self.products

    def record_producer(self, product: str) -> None:
        self.producer_calls[product] = int(self.producer_calls.get(product, 0)) + 1

    def due(self, product: str, now: float, *, force: bool = False) -> bool:
        """Return True if product should be emitted at wall-clock `now`."""
        if not self.wants(product):
            return False
        if force:
            return True
        hz = float(DEFAULT_CADENCE_HZ.get(product, 2.0))
        period = 1.0 / max(1e-3, hz)
        last = float(self._last_emit.get(product, 0.0))
        if (now - last) >= period:
            return True
        return False

    def mark_emitted(self, product: str, now: float) -> None:
        self._last_emit[product] = float(now)

    def replace_from_client(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        """Replace interest from a client message (no duplicate accumulation)."""
        data = payload or {}
        if "preset" in data and str(data.get("preset") or "").upper() in PRESETS:
            return self.set_preset(str(data["preset"]))
        if "products" in data and isinstance(data["products"], (list, tuple, set)):
            return self.set_products(data["products"])
        return self.snapshot()


def stub_deferred(product: str) -> dict[str, Any]:
    return {
        "status": "DEFERRED",
        "product": product,
        "reason": "unsubscribed",
        "observer_only": True,
    }
