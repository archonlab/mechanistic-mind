"""Two independent transferable stocks with complementary conversion.

A: retained local stock (large capacity, slow body leakage).
B: volatile local stock (small capacity, faster body leakage).
Neither is food, oxygen, or metabolism.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from mechanistic_mind.physical_body.config import PhysicalBodyConfig
from mechanistic_mind.physical_body.state import PhysicalBodyState
from mechanistic_mind.planet.state import PlanetState
from mechanistic_mind.physical_system.body_deformation import rest_geometry
from mechanistic_mind.physical_system.body_orientation import oriented_site_cells
from mechanistic_mind.physical_system.environmental_resource import ensure_world_R


@dataclass
class ComplementaryResourcesConfig:
    """Fresh default ON after promotion; from_dict missing → OFF (historical R path)."""

    mode: str = "EXPERIMENTAL"
    transfer_A_enabled: bool = True
    transfer_B_enabled: bool = True
    conversion_enabled: bool = True
    stoich_A: float = 1.0
    stoich_B: float = 1.0
    conversion_rate: float = 0.05
    conversion_efficiency: float = 0.70
    conversion_coeff: float = 1.0
    A_transfer_rate: float = 0.07
    B_transfer_rate: float = 0.12
    A_transfer_loss: float = 0.05
    B_transfer_loss: float = 0.05
    A_site_capacity: float = 1.20
    B_site_capacity: float = 0.22
    A_passive_loss: float = 0.004
    B_passive_loss: float = 0.12
    B_env_source_rate: float = 0.0  # explicit per-cell environmental source term

    @property
    def enabled(self) -> bool:
        return str(self.mode).upper() == "EXPERIMENTAL"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ComplementaryResourcesConfig":
        if not data:
            return cls(mode="OFF")
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


def ensure_field(planet: PlanetState, name: str) -> np.ndarray:
    h, w = planet.T.shape
    arr = getattr(planet, name, None)
    if arr is None or np.asarray(arr).shape != (h, w):
        setattr(planet, name, np.zeros((h, w), dtype=np.float64))
    else:
        setattr(planet, name, np.asarray(arr, dtype=np.float64))
    out = getattr(planet, name)
    np.clip(out, 0.0, None, out=out)
    return out


def ensure_site(body: PhysicalBodyState, name: str, n: int) -> np.ndarray:
    cur = getattr(body, name, None)
    if cur is None or np.asarray(cur).shape != (n,):
        setattr(body, name, np.zeros(n, dtype=np.float64))
    else:
        setattr(body, name, np.asarray(cur, dtype=np.float64))
    out = getattr(body, name)
    np.clip(out, 0.0, None, out=out)
    return out


def place_source_AB(planet: PlanetState, iy: int, ix: int, *, A: float = 0.0, B: float = 0.0) -> dict[str, Any]:
    RA = ensure_field(planet, "R_A")
    RB = ensure_field(planet, "R_B")
    h, w = RA.shape
    iy = int(iy) % h
    ix = int(ix) % w
    if A > 0:
        RA[iy, ix] = float(A)
    if B > 0:
        RB[iy, ix] = float(B)
    return {"iy": iy, "ix": ix, "A": float(RA[iy, ix]), "B": float(RB[iy, ix])}


def _site_cells(body, planet, body_cfg):
    h, w = planet.T.shape
    rest = rest_geometry(body_cfg.footprint)
    d = getattr(body, "deformation", None)
    r_body = rest + np.asarray(d, dtype=np.float64) if d is not None and np.asarray(d).shape == rest.shape else rest
    theta = float(getattr(body, "theta", 0.0) or 0.0)
    return oriented_site_cells(body, w, h, body_cfg.footprint, theta=theta, r_body=r_body)


def _transfer_one(
    *,
    env: np.ndarray,
    store: np.ndarray,
    cells: list[tuple[int, int]],
    rate: float,
    loss_frac: float,
    cap: float,
    enabled: bool,
    tick: int,
    tag: str,
) -> dict[str, Any]:
    removed = acquired = lost = 0.0
    transfers: list[dict[str, Any]] = []
    active: list[int] = []
    cap_sites: list[int] = []
    depleted: list[list[int]] = []
    if not enabled or rate <= 0:
        return {
            "removed": 0.0, "acquired": 0.0, "loss": 0.0, "residual": 0.0,
            "transfers": [], "active": [], "capacity_sites": [], "depleted": [],
        }
    loss_frac = min(max(0.0, loss_frac), 1.0)
    for si, (iy, ix) in enumerate(cells):
        room = max(0.0, cap - float(store[si]))
        avail = float(env[iy, ix])
        if room <= 1e-15:
            if float(store[si]) >= cap - 1e-12:
                cap_sites.append(si)
            continue
        if avail <= 1e-15:
            continue
        if loss_frac >= 1.0:
            remove_i, acq_i = min(rate, avail), 0.0
        else:
            remove_i = min(rate, avail, room / (1.0 - loss_frac))
            acq_i = remove_i * (1.0 - loss_frac)
        loss_i = remove_i - acq_i
        if remove_i <= 1e-15:
            continue
        env[iy, ix] = float(max(0.0, avail - remove_i))
        store[si] = float(min(cap, float(store[si]) + acq_i))
        removed += remove_i
        acquired += acq_i
        lost += loss_i
        active.append(si)
        transfers.append({
            "site": si, "cell": [int(iy), int(ix)], "source_id": f"cell:{iy},{ix}",
            "removed": float(remove_i), "acquired": float(acq_i), "loss": float(loss_i),
            "receipt_id": f"{tag}-{tick}-s{si}",
        })
        if float(env[iy, ix]) <= 1e-12 and avail > 1e-12:
            depleted.append([int(iy), int(ix)])
        if float(store[si]) >= cap - 1e-12:
            cap_sites.append(si)
    return {
        "removed": float(removed), "acquired": float(acquired), "loss": float(lost),
        "residual": float(removed - acquired - lost),
        "transfers": transfers, "active": active, "capacity_sites": cap_sites, "depleted": depleted,
    }


def step_complementary_resources(
    body: PhysicalBodyState,
    planet: PlanetState,
    body_cfg: PhysicalBodyConfig,
    cfg: ComplementaryResourcesConfig,
    deform_work_cfg: Any | None = None,
    *,
    receipt_tick: int = 0,
) -> dict[str, Any]:
    n = len(body_cfg.footprint)
    RA = ensure_field(planet, "R_A")
    RB = ensure_field(planet, "R_B")
    A_site = ensure_site(body, "R_A_site", n)
    B_site = ensure_site(body, "R_B_site", n)
    W0 = float(getattr(body, "mechanical_work_reservoir", 0.0) or 0.0)
    W_max = float(getattr(deform_work_cfg, "reservoir_max", 4.0) or 4.0)
    b_src = 0.0
    if cfg.enabled and cfg.B_env_source_rate > 0:
        inc = float(cfg.B_env_source_rate)
        RB += inc
        b_src = float(inc * RB.size)

    empty = {
        "enabled": bool(cfg.enabled),
        "work_credited": 0.0,
        "limiting_resource": "NONE",
        "consumed_A": 0.0,
        "consumed_B": 0.0,
        "reservoir_before": W0,
        "reservoir_after": W0,
        "A": {},
        "B": {},
        "conversion": {},
        "where_did_this_work_come_from": [],
    }
    if not cfg.enabled:
        empty["env_A"] = float(RA.sum())
        empty["env_B"] = float(RB.sum())
        empty["body_A"] = float(A_site.sum())
        empty["body_B"] = float(B_site.sum())
        return empty

    cells = _site_cells(body, planet, body_cfg)
    tA = _transfer_one(
        env=RA, store=A_site, cells=cells, rate=cfg.A_transfer_rate,
        loss_frac=cfg.A_transfer_loss, cap=cfg.A_site_capacity,
        enabled=cfg.transfer_A_enabled, tick=receipt_tick, tag="A",
    )
    tB = _transfer_one(
        env=RB, store=B_site, cells=cells, rate=cfg.B_transfer_rate,
        loss_frac=cfg.B_transfer_loss, cap=cfg.B_site_capacity,
        enabled=cfg.transfer_B_enabled, tick=receipt_tick, tag="B",
    )

    A_pass = 0.0
    B_pass = 0.0
    for i in range(n):
        la = min(float(A_site[i]), float(A_site[i]) * max(0.0, cfg.A_passive_loss))
        lb = min(float(B_site[i]), float(B_site[i]) * max(0.0, cfg.B_passive_loss))
        A_site[i] = float(max(0.0, A_site[i] - la))
        B_site[i] = float(max(0.0, B_site[i] - lb))
        A_pass += la
        B_pass += lb

    consumed_A = consumed_B = 0.0
    work_credit = conv_loss = 0.0
    limiting_counts = {"A": 0, "B": 0, "RATE": 0, "WORK_CAPACITY": 0, "NONE": 0}
    eta = min(max(0.0, float(cfg.conversion_efficiency)), 1.0)
    kappa = float(cfg.conversion_coeff)
    sa, sb = max(1e-12, float(cfg.stoich_A)), max(1e-12, float(cfg.stoich_B))
    crate = max(0.0, float(cfg.conversion_rate))
    W = W0
    site_conv: list[dict[str, Any]] = []
    if cfg.conversion_enabled and crate > 0 and kappa > 0:
        room_w = max(0.0, W_max - W)
        for i in range(n):
            if room_w <= 1e-15:
                limiting_counts["WORK_CAPACITY"] += 1
                break
            avail_A = float(A_site[i]) / sa
            avail_B = float(B_site[i]) / sb
            max_from_w = room_w / max(eta * kappa, 1e-15) if eta > 0 else 0.0
            n_rxn = min(avail_A, avail_B, crate, max_from_w)
            if n_rxn <= 1e-15:
                if avail_A <= 1e-15 and avail_B <= 1e-15:
                    limiting_counts["NONE"] += 1
                elif avail_A <= avail_B:
                    limiting_counts["A"] += 1
                else:
                    limiting_counts["B"] += 1
                continue
            opts = [("A", avail_A), ("B", avail_B), ("RATE", crate), ("WORK_CAPACITY", max_from_w)]
            lim = min(opts, key=lambda x: x[1])[0]
            limiting_counts[lim] += 1
            dA, dB = n_rxn * sa, n_rxn * sb
            A_site[i] = float(max(0.0, A_site[i] - dA))
            B_site[i] = float(max(0.0, B_site[i] - dB))
            dW = eta * kappa * n_rxn
            W = min(W_max, W + dW)
            room_w = max(0.0, W_max - W)
            consumed_A += dA
            consumed_B += dB
            work_credit += dW
            conv_loss += (1.0 - eta) * kappa * n_rxn
            site_conv.append({"site": i, "n": float(n_rxn), "limiting": lim, "dW": float(dW)})

    body.R_A_site = A_site
    body.R_B_site = B_site
    body.mechanical_work_reservoir = float(W)
    n_tot = consumed_A / sa if sa else 0.0
    conv_residual = work_credit + conv_loss - kappa * n_tot

    lim_label = "NONE"
    if work_credit <= 1e-15:
        if float(A_site.sum()) > 1e-9 and float(B_site.sum()) <= 1e-9:
            lim_label = "B"
        elif float(B_site.sum()) > 1e-9 and float(A_site.sum()) <= 1e-9:
            lim_label = "A"
        elif consumed_A <= 1e-15:
            lim_label = "NONE"
    else:
        lim_label = max((k for k in ("A", "B", "RATE", "WORK_CAPACITY") if limiting_counts[k]), key=lambda k: limiting_counts[k], default="NONE")

    sources = []
    if work_credit > 1e-12:
        sources.append("COMPLEMENTARY_CONVERSION")
        sources.append("BODY_R_A_AND_R_B")

    return {
        "enabled": True,
        "transfer_A_enabled": bool(cfg.transfer_A_enabled),
        "transfer_B_enabled": bool(cfg.transfer_B_enabled),
        "conversion_enabled": bool(cfg.conversion_enabled),
        "env_A": float(RA.sum()),
        "env_B": float(RB.sum()),
        "body_A": float(A_site.sum()),
        "body_B": float(B_site.sum()),
        "R_A_site": A_site.tolist(),
        "R_B_site": B_site.tolist(),
        "B_env_source": float(b_src),
        "A": {**tA, "passive_loss": float(A_pass), "capacity": cfg.A_site_capacity},
        "B": {**tB, "passive_loss": float(B_pass), "capacity": cfg.B_site_capacity, "passive_sink": "BODY_DISSIPATIVE_LEAK"},
        "consumed_A": float(consumed_A),
        "consumed_B": float(consumed_B),
        "work_credited": float(work_credit),
        "conversion_loss_work": float(conv_loss),
        "conversion_residual": float(conv_residual),
        "reservoir_before": W0,
        "reservoir_after": float(W),
        "limiting_resource": lim_label,
        "limiting_counts": limiting_counts,
        "stoich": {"A": sa, "B": sb, "eta": eta, "kappa": kappa},
        "site_conversion": site_conv,
        "where_did_this_work_come_from": sources,
        "note": "Complementary stocks A/B; not food, oxygen, or metabolism.",
    }


def _desired_draws(
    *,
    env: np.ndarray,
    store: np.ndarray,
    cells: list[tuple[int, int]],
    rate: float,
    loss_frac: float,
    cap: float,
    enabled: bool,
) -> list[tuple[int, int, int, float, float]]:
    """(si, iy, ix, remove, acquire) against a frozen env snapshot; does not mutate."""
    out: list[tuple[int, int, int, float, float]] = []
    if not enabled or rate <= 0:
        return out
    loss_frac = min(max(0.0, loss_frac), 1.0)
    for si, (iy, ix) in enumerate(cells):
        room = max(0.0, cap - float(store[si]))
        avail = float(env[iy, ix])
        if room <= 1e-15 or avail <= 1e-15:
            continue
        if loss_frac >= 1.0:
            remove_i, acq_i = min(rate, avail), 0.0
        else:
            remove_i = min(rate, avail, room / (1.0 - loss_frac))
            acq_i = remove_i * (1.0 - loss_frac)
        if remove_i > 1e-15:
            out.append((int(si), int(iy), int(ix), float(remove_i), float(acq_i)))
    return out


def simultaneous_complementary_resources(
    bodies: list[PhysicalBodyState],
    planet: PlanetState,
    body_cfgs: list[PhysicalBodyConfig],
    cfg: ComplementaryResourcesConfig,
    deform_work_cfg: Any | None = None,
    *,
    receipt_tick: int = 0,
) -> list[dict[str, Any]]:
    """One-tick env draw from a frozen stock snapshot. Contested cells are flux-limited.

    If several bodies request more than a cell holds, each draw is scaled by
    available/sum(requested). This is a physical conservation rule, not a social policy.
    Conversion remains per-body after transfer.
    """
    RA = ensure_field(planet, "R_A")
    RB = ensure_field(planet, "R_B")
    snap_A = np.asarray(RA, dtype=np.float64).copy()
    snap_B = np.asarray(RB, dtype=np.float64).copy()
    n_agents = len(bodies)
    cells_list = [_site_cells(bodies[i], planet, body_cfgs[i]) for i in range(n_agents)]
    stores_A = [ensure_site(bodies[i], "R_A_site", len(body_cfgs[i].footprint)) for i in range(n_agents)]
    stores_B = [ensure_site(bodies[i], "R_B_site", len(body_cfgs[i].footprint)) for i in range(n_agents)]
    desired_A: list[list[tuple[int, int, int, float, float]]] = []
    desired_B: list[list[tuple[int, int, int, float, float]]] = []
    for i in range(n_agents):
        desired_A.append(_desired_draws(
            env=snap_A, store=stores_A[i], cells=cells_list[i],
            rate=cfg.A_transfer_rate, loss_frac=cfg.A_transfer_loss,
            cap=cfg.A_site_capacity, enabled=bool(cfg.enabled and cfg.transfer_A_enabled),
        ))
        desired_B.append(_desired_draws(
            env=snap_B, store=stores_B[i], cells=cells_list[i],
            rate=cfg.B_transfer_rate, loss_frac=cfg.B_transfer_loss,
            cap=cfg.B_site_capacity, enabled=bool(cfg.enabled and cfg.transfer_B_enabled),
        ))

    def _apply(field: np.ndarray, desired_all: list[list[tuple[int, int, int, float, float]]], stores: list[np.ndarray], cap: float):
        demand: dict[tuple[int, int], float] = {}
        for rows in desired_all:
            for _si, iy, ix, rem, _acq in rows:
                demand[(iy, ix)] = demand.get((iy, ix), 0.0) + rem
        scale = {}
        for (iy, ix), dem in demand.items():
            avail = float(field[iy, ix])
            scale[(iy, ix)] = 1.0 if dem <= avail + 1e-15 else (avail / dem if dem > 0 else 0.0)
        applied = []
        for i, rows in enumerate(desired_all):
            removed = acquired = 0.0
            for si, iy, ix, rem, acq in rows:
                s = scale.get((iy, ix), 1.0)
                rem_s, acq_s = rem * s, acq * s
                field[iy, ix] = float(max(0.0, float(field[iy, ix]) - rem_s))
                stores[i][si] = float(min(cap, float(stores[i][si]) + acq_s))
                removed += rem_s
                acquired += acq_s
            applied.append({"removed": removed, "acquired": acquired, "scale_min": min(scale.values()) if scale else 1.0})
        return applied

    app_A = _apply(RA, desired_A, stores_A, cfg.A_site_capacity)
    app_B = _apply(RB, desired_B, stores_B, cfg.B_site_capacity)
    ledgers = []
    saved_A, saved_B = cfg.transfer_A_enabled, cfg.transfer_B_enabled
    cfg.transfer_A_enabled = False
    cfg.transfer_B_enabled = False
    try:
        for i in range(n_agents):
            bodies[i].R_A_site = stores_A[i]
            bodies[i].R_B_site = stores_B[i]
            led = step_complementary_resources(
                bodies[i], planet, body_cfgs[i], cfg, deform_work_cfg, receipt_tick=receipt_tick,
            )
            led["A"] = {**(led.get("A") or {}), **app_A[i], "simultaneous": True}
            led["B"] = {**(led.get("B") or {}), **app_B[i], "simultaneous": True}
            led["simultaneous_allocation"] = True
            ledgers.append(led)
    finally:
        cfg.transfer_A_enabled = saved_A
        cfg.transfer_B_enabled = saved_B
    return ledgers

