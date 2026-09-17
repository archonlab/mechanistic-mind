"""MM-ANALYZER-1 — provenance-backed Physical World scientific summaries.

Read-only. No physics writes. Strict claim strata; refuses unsupported elevations.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from mechanistic_mind.planet.boundary import LAW_VERSION

from .planet_model import PlanetDisplayState

STRATUM_RAW = "RAW_FACT"
STRATUM_DERIVED = "DERIVED_MEASUREMENT"
STRATUM_INTERP = "SUPPORTED_INTERPRETATION"
STRATUM_NULL = "NULL_RESULT"
STRATUM_UNSUPPORTED = "UNSUPPORTED_CLAIM"

ANALYZER_VERSION = "mm_analyzer1_v1"


@dataclass(frozen=True, slots=True)
class AnalyzerClaim:
    stratum: str
    key: str
    text: str
    value: Any = None
    provenance: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "stratum": self.stratum,
            "key": self.key,
            "text": self.text,
            "value": self.value,
            "provenance": self.provenance,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class AnalyzerReport:
    analyzer_version: str
    tick: int
    seed: int | None
    source: str
    claims: tuple[AnalyzerClaim, ...]
    summary_text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "analyzer_version": self.analyzer_version,
            "tick": self.tick,
            "seed": self.seed,
            "source": self.source,
            "claims": [c.to_dict() for c in self.claims],
            "summary_text": self.summary_text,
            "stratum_counts": stratum_counts(self.claims),
        }


def stratum_counts(claims: Sequence[AnalyzerClaim]) -> dict[str, int]:
    out = {
        STRATUM_RAW: 0,
        STRATUM_DERIVED: 0,
        STRATUM_INTERP: 0,
        STRATUM_NULL: 0,
        STRATUM_UNSUPPORTED: 0,
    }
    for c in claims:
        if c.stratum in out:
            out[c.stratum] += 1
    return out


def _raw(key: str, text: str, value: Any, provenance: str, notes: str = "") -> AnalyzerClaim:
    return AnalyzerClaim(STRATUM_RAW, key, text, value, provenance, notes)


def _der(key: str, text: str, value: Any, provenance: str, notes: str = "") -> AnalyzerClaim:
    return AnalyzerClaim(STRATUM_DERIVED, key, text, value, provenance, notes)


def _interp(key: str, text: str, value: Any, provenance: str, notes: str = "") -> AnalyzerClaim:
    return AnalyzerClaim(STRATUM_INTERP, key, text, value, provenance, notes)


def _null(key: str, text: str, provenance: str, notes: str = "") -> AnalyzerClaim:
    return AnalyzerClaim(STRATUM_NULL, key, text, None, provenance, notes)


def _unsup(key: str, text: str, notes: str = "") -> AnalyzerClaim:
    return AnalyzerClaim(
        STRATUM_UNSUPPORTED,
        key,
        text,
        None,
        "refused",
        notes or "Analyzer must not assert this class",
    )


def analyze_physical_world(
    display: PlanetDisplayState,
    *,
    history: Sequence[Mapping[str, Any]] | None = None,
) -> AnalyzerReport:
    """Build stratified claims from a canonical PlanetDisplayState."""
    claims: list[AnalyzerClaim] = []
    s = display.stats or {}
    b = display.boundary

    # --- RAW ---
    claims.append(_raw("tick", f"tick = {display.tick}", display.tick, "PlanetDisplayState.tick"))
    claims.append(
        _raw(
            "dims",
            f"grid = {display.height}×{display.width}, topology = {display.topology}",
            {"height": display.height, "width": display.width, "topology": display.topology},
            "PlanetDisplayState.height/width/topology",
        )
    )
    claims.append(
        _raw(
            "source_seed",
            f"source = {display.source}, seed = {display.seed}",
            {"source": display.source, "seed": display.seed},
            "PlanetDisplayState.source/seed",
        )
    )
    for key in ("T_mean", "T_min", "T_max", "M0_sum", "M1_sum", "M2_sum", "M_total", "matter_err", "speed_mean", "speed_max", "u_abs_mean", "u_abs_max"):
        if key in s:
            claims.append(
                _raw(
                    key,
                    f"{key} = {s[key]!r}",
                    s[key],
                    f"PlanetDisplayState.stats[{key!r}] ← snapshot_stats",
                )
            )

    claims.append(
        _raw(
            "boundary_enabled",
            f"external_material_boundary.enabled = {bool(b.enabled)}",
            bool(b.enabled),
            "PlanetDisplayState.boundary.enabled",
        )
    )
    if b.enabled:
        claims.append(
            _raw(
                "boundary_law",
                f"boundary law_version = {b.law_version}",
                b.law_version,
                "PlanetDisplayState.boundary.law_version",
            )
        )
        claims.append(
            _raw("boundary_K", f"K = {b.K}", b.K, "PlanetDisplayState.boundary.K")
        )
        claims.append(
            _raw(
                "boundary_M_ext",
                f"M_ext = {b.M_ext}",
                b.M_ext,
                "PlanetDisplayState.boundary.M_ext",
            )
        )
        claims.append(
            _raw(
                "boundary_contact_count",
                f"contact_count = {b.contact_count}",
                b.contact_count,
                "PlanetDisplayState.boundary.contact_count",
            )
        )
        claims.append(
            _raw(
                "boundary_mask_sha256",
                f"mask_sha256 = {b.mask_sha256}",
                b.mask_sha256,
                "PlanetDisplayState.boundary.mask_sha256",
            )
        )
        claims.append(
            _raw(
                "last_signed_flux",
                f"last_signed_flux = {b.last_signed_flux}",
                b.last_signed_flux,
                "PlanetDisplayState.boundary.last_signed_flux",
            )
        )
        claims.append(
            _raw(
                "cum_import",
                f"cum_import = {b.cum_import}",
                b.cum_import,
                "PlanetDisplayState.boundary.cum_import",
            )
        )
        claims.append(
            _raw(
                "cum_export",
                f"cum_export = {b.cum_export}",
                b.cum_export,
                "PlanetDisplayState.boundary.cum_export",
            )
        )
        claims.append(
            _raw(
                "last_residual_max",
                f"last_residual_max = {b.last_residual_max}",
                b.last_residual_max,
                "PlanetDisplayState.boundary.last_residual_max",
            )
        )
        claims.append(
            _raw(
                "accounting_tol",
                f"accounting_tol = {b.accounting_tol}",
                b.accounting_tol,
                "PlanetDisplayState.boundary.accounting_tol",
            )
        )

    # --- DERIVED ---
    if b.enabled:
        net = b.net_flux
        claims.append(
            _der(
                "net_flux",
                f"net_flux (= import − export) = {net}",
                net,
                "BoundaryDisplay.net_flux ← cum_import − cum_export",
            )
        )
        claims.append(
            _der(
                "residual_within_tolerance",
                f"residual_within_tolerance = {b.residual_within_tolerance}",
                bool(b.residual_within_tolerance),
                "BoundaryDisplay.residual_within_tolerance ← last_residual_max ≤ accounting_tol",
            )
        )

    hist = list(history) if history is not None else []
    if len(hist) >= 2:
        t0 = hist[0]
        t1 = hist[-1]
        dM0 = None
        if t0.get("M0_sum") is not None and t1.get("M0_sum") is not None:
            dM0 = float(t1["M0_sum"]) - float(t0["M0_sum"])
            claims.append(
                _der(
                    "delta_M0_sum_history",
                    f"ΔM0_sum over history window = {dM0}",
                    dM0,
                    "BoundedScalarHistory[0..-1].M0_sum difference",
                    notes=f"window ticks {t0.get('tick')}→{t1.get('tick')} (maxlen-bounded)",
                )
            )
        d_imp = None
        if t0.get("import_sum") is not None and t1.get("import_sum") is not None:
            d_imp = float(t1["import_sum"]) - float(t0["import_sum"])
            claims.append(
                _der(
                    "delta_import_sum_history",
                    f"Δcumulative_import_sum over history = {d_imp}",
                    d_imp,
                    "BoundedScalarHistory import_sum difference",
                )
            )
    else:
        claims.append(
            _null(
                "history_deltas",
                "History-derived ΔM / Δimport not available (need ≥2 history rows)",
                "PlanetInspectionSession.history",
                notes=f"history_len={len(hist)}",
            )
        )

    # --- SUPPORTED INTERPRETATIONS (contract-backed only) ---
    if not b.enabled:
        claims.append(
            _interp(
                "boundary_off_no_exchange",
                "External material boundary is OFF; no OPEN-6 material exchange is active on this state.",
                True,
                "OPEN-6 default-OFF + BoundaryDisplay.enabled=False",
            )
        )
    else:
        if b.law_version == LAW_VERSION:
            claims.append(
                _interp(
                    "boundary_on_known_law",
                    f"Boundary ON under production law {LAW_VERSION}.",
                    True,
                    "OPEN-6 LAW_VERSION match",
                )
            )
        else:
            claims.append(
                _null(
                    "boundary_law_detail",
                    "Boundary ON but law_version ≠ production LAW_VERSION; interpretation limited to raw metadata.",
                    "PlanetDisplayState.boundary.law_version vs LAW_VERSION",
                )
            )
        if b.residual_within_tolerance:
            claims.append(
                _interp(
                    "accounting_ok",
                    "Boundary accounting residual is within production tolerance.",
                    True,
                    "OPEN-6 accounting residual ≤ ACCOUNTING_TOL",
                )
            )
        else:
            claims.append(
                _interp(
                    "accounting_above_tol",
                    "Boundary accounting residual is ABOVE production tolerance (reported, not repaired).",
                    True,
                    "OPEN-6 residual check",
                )
            )

    # matter_err is raw; interpretation only as accounting identity signal, not "leak story"
    if "matter_err" in s:
        claims.append(
            _interp(
                "matter_err_is_reported_balance",
                "matter_err is the reported M_total − matter_initial balance from snapshot_stats (not a causal leak diagnosis).",
                float(s["matter_err"]),
                "snapshot_stats.matter_err definition",
            )
        )

    # --- NULL (honest absences on PW path) ---
    claims.append(
        _null(
            "local_J_overlay_map",
            "Full-grid local J overlay map is NOT_IMPLEMENTED on Observer (ephemeral per-cell only).",
            "MM-OBS-1 contract",
        )
    )
    claims.append(
        _null(
            "body_state",
            "PhysicalBody state is not part of Physical World zero-organism inspection path.",
            "MM-CONFIG-1 / PlanetInspectionSession",
        )
    )
    claims.append(
        _null(
            "internal_substrate_state",
            "Internal substrate / medium state is not part of Physical World inspection path.",
            "MM-CONFIG-1 / PlanetInspectionSession",
        )
    )
    claims.append(
        _null(
            "organism_cognition",
            "Organism / psyche / Agent telemetry is not grounded in Physical World GT on this path.",
            "MM-OBS-REDESIGN-1 ground-truth firewall",
        )
    )

    # --- UNSUPPORTED (refused claim classes; listed so UI can show the fence) ---
    for key, text in (
        (
            "refuse_environment_semantics",
            "UNSUPPORTED: assigning ecological meaning / habitat narrative to M_ext or mask geometry.",
        ),
        (
            "refuse_life_agency",
            "UNSUPPORTED: claims that Planet fields constitute life, agency, or intention.",
        ),
        (
            "refuse_psyche_causation",
            "UNSUPPORTED: causal claims from Planet fields to psyche/behavior without a BODY+INTERNAL Observer path.",
        ),
        (
            "refuse_invented_defaults",
            "UNSUPPORTED: inventing mask/K/M_ext defaults not present on the display.",
        ),
    ):
        claims.append(_unsup(key, text))

    summary = format_analyzer_summary(tuple(claims), display)
    return AnalyzerReport(
        analyzer_version=ANALYZER_VERSION,
        tick=int(display.tick),
        seed=display.seed,
        source=str(display.source),
        claims=tuple(claims),
        summary_text=summary,
    )


def format_analyzer_summary(
    claims: Sequence[AnalyzerClaim],
    display: PlanetDisplayState,
) -> str:
    """Human-readable summary with explicit stratum sections."""
    by: dict[str, list[AnalyzerClaim]] = {
        STRATUM_RAW: [],
        STRATUM_DERIVED: [],
        STRATUM_INTERP: [],
        STRATUM_NULL: [],
        STRATUM_UNSUPPORTED: [],
    }
    for c in claims:
        by.setdefault(c.stratum, []).append(c)

    lines = [
        "PHYSICAL WORLD ANALYZER",
        f"version={ANALYZER_VERSION}  tick={display.tick}  seed={display.seed}  source={display.source}",
        "Strata are separated: RAW ≠ DERIVED ≠ INTERPRETATION ≠ NULL ≠ UNSUPPORTED.",
        "",
        f"=== {STRATUM_RAW} ===",
    ]
    for c in by[STRATUM_RAW]:
        lines.append(f"• {c.text}")
        if c.provenance:
            lines.append(f"    provenance: {c.provenance}")
    lines.append("")
    lines.append(f"=== {STRATUM_DERIVED} ===")
    if by[STRATUM_DERIVED]:
        for c in by[STRATUM_DERIVED]:
            lines.append(f"• {c.text}")
            lines.append(f"    provenance: {c.provenance}")
    else:
        lines.append("• (none)")
    lines.append("")
    lines.append(f"=== {STRATUM_INTERP} ===")
    for c in by[STRATUM_INTERP]:
        lines.append(f"• {c.text}")
        lines.append(f"    provenance: {c.provenance}")
    lines.append("")
    lines.append(f"=== {STRATUM_NULL} ===")
    for c in by[STRATUM_NULL]:
        lines.append(f"• {c.text}")
        lines.append(f"    provenance: {c.provenance}")
    lines.append("")
    lines.append(f"=== {STRATUM_UNSUPPORTED} (refused) ===")
    for c in by[STRATUM_UNSUPPORTED]:
        lines.append(f"• {c.text}")
    return "\n".join(lines)


def claims_by_stratum(report: AnalyzerReport, stratum: str) -> tuple[AnalyzerClaim, ...]:
    return tuple(c for c in report.claims if c.stratum == stratum)


def assert_no_stratum_elevation(report: AnalyzerReport) -> None:
    """Structural guard: NULL/UNSUPPORTED keys must not also appear as INTERP."""
    null_keys = {c.key for c in report.claims if c.stratum == STRATUM_NULL}
    unsup_keys = {c.key for c in report.claims if c.stratum == STRATUM_UNSUPPORTED}
    interp_keys = {c.key for c in report.claims if c.stratum == STRATUM_INTERP}
    overlap = (null_keys | unsup_keys) & interp_keys
    if overlap:
        raise AssertionError(f"stratum elevation detected for keys: {sorted(overlap)}")
