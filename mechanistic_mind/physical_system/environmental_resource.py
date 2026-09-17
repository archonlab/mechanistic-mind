"""Finite transferable_resource: env cell stock → body-local R_site → work reservoir.

Neutral physical quantity. Not food, calories, metabolism, or reward.
Units of R are explicit resource units; conversion to mechanical work uses
documented coefficient κ and efficiency η:

    ΔW = η * κ * consumed_R
    conversion_loss_R = (1 - η) * consumed_R   (resource not appearing as work)

Environment field planet.R[iy, ix] is the source stock at that cell.
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


@dataclass
class EnvironmentalResourceConfig:
    """Fresh CURRENT INTEGRATED default ON; from_dict missing → OFF."""

    mode: str = "EXPERIMENTAL"
    transfer_enabled: bool = True
    conversion_enabled: bool = True
    transfer_rate: float = 0.08
    transfer_loss: float = 0.05  # fraction of removed env stock that never arrives
    site_capacity: float = 1.0
    conversion_rate: float = 0.06
    conversion_efficiency: float = 0.70
    conversion_coeff: float = 1.0  # work units per acquired-resource unit before η

    @property
    def enabled(self) -> bool:
        return str(self.mode).upper() == "EXPERIMENTAL"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "EnvironmentalResourceConfig":
        if not data:
            return cls(mode="OFF")
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


def ensure_world_R(planet: PlanetState) -> np.ndarray:
    h, w = planet.T.shape
    R = getattr(planet, "R", None)
    if R is None or np.asarray(R).shape != (h, w):
        planet.R = np.zeros((h, w), dtype=np.float64)
    else:
        planet.R = np.asarray(R, dtype=np.float64)
    np.clip(planet.R, 0.0, None, out=planet.R)
    return planet.R


def ensure_R_site(body: PhysicalBodyState, n_sites: int) -> np.ndarray:
    current = getattr(body, "R_site", None)
    if current is None or np.asarray(current).shape != (n_sites,):
        body.R_site = np.zeros(n_sites, dtype=np.float64)
    else:
        body.R_site = np.asarray(current, dtype=np.float64)
    np.clip(body.R_site, 0.0, None, out=body.R_site)
    return body.R_site


def place_source(planet: PlanetState, iy: int, ix: int, amount: float) -> dict[str, Any]:
    R = ensure_world_R(planet)
    h, w = R.shape
    iy = int(iy) % h
    ix = int(ix) % w
    R[iy, ix] = float(max(0.0, amount))
    return {"iy": iy, "ix": ix, "stock": float(R[iy, ix]), "id": f"cell:{iy},{ix}"}


def empty_resource_ledger(n_sites: int = 0) -> dict[str, Any]:
    return {
        "enabled": False,
        "transfer_enabled": False,
        "conversion_enabled": False,
        "env_R_sum": 0.0,
        "body_R_sum": 0.0,
        "removed_from_env": 0.0,
        "acquired_by_body": 0.0,
        "transfer_loss": 0.0,
        "transfer_residual": 0.0,
        "converted_R": 0.0,
        "work_credited": 0.0,
        "conversion_loss_work": 0.0,
        "conversion_residual": 0.0,
        "reservoir_before": 0.0,
        "reservoir_after": 0.0,
        "active_sites": [],
        "site_transfers": [],
        "where_did_this_work_come_from": [],
        "capacity_reached_sites": [],
        "source_depleted_cells": [],
    }


def step_environmental_resource(
    body: PhysicalBodyState,
    planet: PlanetState,
    body_cfg: PhysicalBodyConfig,
    cfg: EnvironmentalResourceConfig,
    deform_work_cfg: Any | None = None,
    *,
    receipt_tick: int = 0,
    skip_conversion: bool = False,
) -> dict[str, Any]:
    n_fp = len(body_cfg.footprint)
    R_env = ensure_world_R(planet)
    R_site = ensure_R_site(body, n_fp)
    h, w = R_env.shape
    env_before = float(R_env.sum())
    body_before = float(R_site.sum())
    W0 = float(getattr(body, "mechanical_work_reservoir", 0.0) or 0.0)
    W_max = float(getattr(deform_work_cfg, "reservoir_max", 4.0) or 4.0)

    ledger = empty_resource_ledger(n_fp)
    ledger.update({
        "enabled": bool(cfg.enabled),
        "transfer_enabled": bool(cfg.enabled and cfg.transfer_enabled),
        "conversion_enabled": bool(cfg.enabled and cfg.conversion_enabled and not skip_conversion),
        "conversion_skipped_due_to_complementary": bool(skip_conversion),
        "env_R_sum_before": env_before,
        "body_R_sum_before": body_before,
        "reservoir_before": W0,
        "site_capacity": float(cfg.site_capacity),
        "conversion_efficiency": float(cfg.conversion_efficiency),
        "conversion_coeff": float(cfg.conversion_coeff),
        "note": "transferable_resource is a generic finite stock; not food or metabolism.",
    })
    if not cfg.enabled:
        ledger["env_R_sum"] = env_before
        ledger["body_R_sum"] = body_before
        ledger["reservoir_after"] = W0
        return ledger

    d = getattr(body, "deformation", None)
    rest = rest_geometry(body_cfg.footprint)
    if d is not None and np.asarray(d).shape == rest.shape:
        r_body = rest + np.asarray(d, dtype=np.float64)
    else:
        r_body = rest
    theta = float(getattr(body, "theta", 0.0) or 0.0)
    cells = oriented_site_cells(body, w, h, body_cfg.footprint, theta=theta, r_body=r_body)

    removed = 0.0
    acquired = 0.0
    lost = 0.0
    site_transfers: list[dict[str, Any]] = []
    active: list[int] = []
    cap_sites: list[int] = []
    depleted: list[list[int]] = []
    loss_frac = min(max(0.0, float(cfg.transfer_loss)), 1.0)
    rate = max(0.0, float(cfg.transfer_rate))
    cap = max(0.0, float(cfg.site_capacity))

    if cfg.transfer_enabled and rate > 0.0:
        for si, (iy, ix) in enumerate(cells):
            room = max(0.0, cap - float(R_site[si]))
            avail = float(R_env[iy, ix])
            if room <= 1e-15:
                if float(R_site[si]) >= cap - 1e-12:
                    cap_sites.append(si)
                continue
            if avail <= 1e-15:
                continue
            if loss_frac >= 1.0:
                remove_i = min(rate, avail)
                acq_i = 0.0
                loss_i = remove_i
            else:
                remove_i = min(rate, avail, room / (1.0 - loss_frac))
                acq_i = remove_i * (1.0 - loss_frac)
                loss_i = remove_i - acq_i
            if remove_i <= 1e-15:
                continue
            R_env[iy, ix] = float(max(0.0, avail - remove_i))
            R_site[si] = float(min(cap, float(R_site[si]) + acq_i))
            removed += remove_i
            acquired += acq_i
            lost += loss_i
            active.append(si)
            rec_id = f"res-{int(receipt_tick)}-s{si}"
            site_transfers.append({
                "site": si,
                "cell": [int(iy), int(ix)],
                "source_id": f"cell:{iy},{ix}",
                "removed": float(remove_i),
                "acquired": float(acq_i),
                "loss": float(loss_i),
                "receipt_id": rec_id,
                "R_site_after": float(R_site[si]),
                "env_after": float(R_env[iy, ix]),
            })
            if float(R_env[iy, ix]) <= 1e-12 and avail > 1e-12:
                depleted.append([int(iy), int(ix)])
            if float(R_site[si]) >= cap - 1e-12:
                cap_sites.append(si)

    transfer_residual = removed - acquired - lost

    converted = 0.0
    work_credit = 0.0
    conv_loss_work = 0.0
    eta = min(max(0.0, float(cfg.conversion_efficiency)), 1.0)
    kappa = float(cfg.conversion_coeff)
    crate = max(0.0, float(cfg.conversion_rate))
    W = W0
    if cfg.conversion_enabled and (not skip_conversion) and crate > 0.0 and kappa > 0.0:
        room_w = max(0.0, W_max - W)
        for si in range(n_fp):
            if room_w <= 1e-15:
                break
            have = float(R_site[si])
            if have <= 1e-15:
                continue
            max_from_room = room_w / max(eta * kappa, 1e-15) if eta > 0 else 0.0
            consume = min(crate, have, max_from_room)
            if consume <= 1e-15:
                continue
            dW = eta * kappa * consume
            R_site[si] = float(max(0.0, have - consume))
            W = min(W_max, W + dW)
            converted += consume
            work_credit += dW
            conv_loss_work += (1.0 - eta) * kappa * consume
            room_w = max(0.0, W_max - W)

    body.R_site = R_site
    body.mechanical_work_reservoir = float(W)
    conv_residual = work_credit + conv_loss_work - kappa * converted

    sources = []
    if work_credit > 1e-12:
        sources.append("CONVERTED_TRANSFERABLE_RESOURCE")
        if site_transfers:
            sources.append("ENVIRONMENT_CELL_STOCK")

    ledger.update({
        "env_R_sum": float(R_env.sum()),
        "body_R_sum": float(R_site.sum()),
        "R_site": R_site.tolist(),
        "cells": [[int(iy), int(ix)] for iy, ix in cells],
        "removed_from_env": float(removed),
        "acquired_by_body": float(acquired),
        "transfer_loss": float(lost),
        "transfer_residual": float(transfer_residual),
        "converted_R": float(converted),
        "work_credited": float(work_credit),
        "conversion_loss_work": float(conv_loss_work),
        "conversion_residual": float(conv_residual),
        "reservoir_after": float(W),
        "active_sites": sorted(set(active)),
        "site_transfers": site_transfers,
        "where_did_this_work_come_from": sources,
        "capacity_reached_sites": sorted(set(cap_sites)),
        "source_depleted_cells": depleted,
        "identity_transfer": "removed = acquired + loss + residual",
        "identity_conversion": "κ * converted_R = work_credited + conversion_loss_work + residual",
    })
    return ledger
