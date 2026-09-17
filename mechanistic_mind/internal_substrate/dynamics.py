"""Physical coupling BODY → internal substrate S. No psyche adapters."""
from __future__ import annotations
import numpy as np

from mechanistic_mind.internal_substrate.config import InternalSubstrateConfig
from mechanistic_mind.internal_substrate.state import InternalSubstrateState
from mechanistic_mind.physical_body.state import PhysicalBodyState


def step_internal_substrate(
    sub: InternalSubstrateState,
    body: PhysicalBodyState,
    cfg: InternalSubstrateConfig,
) -> InternalSubstrateState:
    if not cfg.substrate_enabled:
        sub.tick += 1
        return sub

    s = sub.s
    dim = cfg.dim
    # --- gather local BODY physical observables (raw fields, not EHF summaries) ---
    T = float(body.T)
    B = body.B.astype(np.float64)
    Bc = body.B_core.astype(np.float64)
    mech = float(body.mech)

    # thermal: baseline kinetic rate; BODY T modulates when channel enabled
    rate = float(cfg.thermal_bias)
    d_thermal = 0.0
    if cfg.thermal_enabled:
        rate = cfg.thermal_bias + cfg.thermal_rate_gain * T
        d_thermal = float(rate)

    # surface chemical potential: composition differences across B components
    chem = np.zeros(dim, dtype=np.float64)
    d_surface = 0.0
    if cfg.surface_enabled:
        # pad/truncate B to dim
        for i in range(min(3, dim)):
            chem[i] = cfg.surface_chem_gain * (float(B[i]) - float(np.mean(B)))
        if dim > 3:
            chem[3] = cfg.surface_chem_gain * (float(B.sum()) - 0.6)
        d_surface = float(np.linalg.norm(chem))

    # core exchange: slow conserved-ish transfer between B_core and s[:3]
    d_core = 0.0
    if cfg.core_enabled:
        for i in range(min(3, dim)):
            df = cfg.core_exchange * (float(Bc[i]) - float(s[i]))
            # move mass-like quantity: s gains, B_core loses (if backreact)
            s[i] = float(s[i] + df)
            if cfg.backreact_core:
                body.B_core[i] = float(np.clip(Bc[i] - df, 0.0, 2.0))
                Bc[i] = body.B_core[i]
            d_core += abs(df)
            sub.core_exchanged += abs(df)

    # mechanical modulation of leak
    leak = cfg.leak
    d_mech = 0.0
    if cfg.mech_enabled:
        d_mech = cfg.mech_mod_gain * abs(mech)
        leak = cfg.leak * (1.0 + d_mech)

    # intrinsic dynamics: leak + weak cyclic self-coupling + chem drive, scaled by thermal rate
    # cyclic neighbor mixing (physical ring on S components)
    mix = np.zeros(dim, dtype=np.float64)
    for i in range(dim):
        mix[i] = cfg.self_couple * (s[(i - 1) % dim] - 2.0 * s[i] + s[(i + 1) % dim])

    ds = rate * (mix + chem) - leak * s
    s = s + ds

    # weak thermal backreact from |activity|
    if cfg.backreact_thermal > 0.0:
        body.T = float(np.clip(body.T + cfg.backreact_thermal * float(np.mean(np.abs(ds))), 0.0, 1.0))

    sub.s = np.clip(s, -cfg.clip_abs, cfg.clip_abs)
    sub.drive_thermal = d_thermal
    sub.drive_surface = d_surface
    sub.drive_core = float(d_core)
    sub.drive_mech = float(d_mech)
    sub.tick += 1
    return sub
