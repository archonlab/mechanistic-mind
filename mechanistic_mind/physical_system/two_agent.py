"""Experimental two-agent runtime: one shared world, two independent MM slots.

Not Tiktaalik canonical default. Technical keys agent_0 / agent_1 never enter
agent observation.

Each slot is a full PhysicalSystemRuntime with:
- independent cognition / body / internal state
- independent agent_seed for endogenous sampling (seed + slot_index)
Shared: PlanetState only (and config copies per slot).
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import numpy as np

from mechanistic_mind.physical_system.body_contact import resolve_soft_contact
from mechanistic_mind.physical_system.physical_push import apply_push_through_contact
from mechanistic_mind.physical_system.complementary_resources import simultaneous_complementary_resources
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.physical_signal import (
    PhysicalSignalConfig,
    _site_cells,
    clear_fields,
    ensure_fields,
    sample_local,
    step_physical_signals,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.planet.dynamics import step_planet


TECHNICAL_IDS = ("agent_0", "agent_1")


def _wrap_delta_1d(a: float, b: float, size: int) -> float:
    """Periodic minimum-image displacement on one axis."""
    d = float(b) - float(a)
    half = float(size) / 2.0
    if d > half:
        d -= float(size)
    elif d < -half:
        d += float(size)
    return d


def agent_seed(base_seed: int, slot_index: int) -> int:
    """Independent endogenous RNG stream per slot. World dynamics keep base_seed."""
    return int(base_seed) + int(slot_index)


def _cfg_with_start(base: PhysicalSystemConfig, x: int, y: int) -> PhysicalSystemConfig:
    cfg = base.copy()
    cfg.body.start_x = int(x)
    cfg.body.start_y = int(y)
    return cfg


def _empty_agent_stats() -> dict[str, Any]:
    return {
        "ticks": 0,
        "action_counts": {},
        "wait_count": 0,
        "move_count": 0,
        "distance_travelled": 0.0,
        "unique_cells": set(),
        "collision_ticks": 0,
        "cognition_ticks": 0,
        "last_competition": None,
    }


class TwoAgentRuntime:
    """One PlanetState. Two PhysicalSystemRuntime slots sharing that world."""

    def __init__(
        self,
        *,
        seed: int = 17,
        config: PhysicalSystemConfig | None = None,
        starts: tuple[tuple[int, int], tuple[int, int]] = ((8, 16), (12, 16)),
        contact_enabled: bool = True,
        field_coupling_enabled: bool = True,
        signal_enabled: bool = False,
        process_order: tuple[int, int] = (0, 1),
        independent_agent_seeds: bool = True,
    ) -> None:
        self.seed = int(seed)
        self.base_config = (config or PhysicalSystemConfig()).copy()
        self.starts = starts
        self.contact_enabled = bool(contact_enabled)
        self.field_coupling_enabled = bool(field_coupling_enabled)
        self.signal_enabled = bool(signal_enabled)
        self.process_order = tuple(process_order)
        self.independent_agent_seeds = bool(independent_agent_seeds)
        self.selected_index = 0
        self.last_contact: dict[str, Any] | None = None
        self.last_contacts: list[dict[str, Any]] = []
        self.last_resource_sim: list[dict[str, Any]] | None = None
        self.last_signal_receipt: dict[str, Any] | None = None
        self._pending_sources: list[dict[str, Any]] = []
        self.slots: list[PhysicalSystemRuntime] = []
        self._agent_stats: list[dict[str, Any]] = []
        self._prev_xy: list[tuple[float, float] | None] = [None, None]
        self.experimenter_slot: int | None = None
        self.reset()

    def reset(self) -> None:
        self.slots = []
        self._agent_stats = [_empty_agent_stats(), _empty_agent_stats()]
        self._prev_xy = [None, None]
        self.experimenter_slot = None
        self.last_contacts = []
        for i, (x, y) in enumerate(self.starts):
            cfg = _cfg_with_start(self.base_config, x, y)
            if not self.field_coupling_enabled:
                cfg.body.thermal_backreact = 0.0
                cfg.body.material_backreact = False
            if self.signal_enabled:
                cfg.physical_signal = PhysicalSignalConfig(mode="EXPERIMENTAL")
            else:
                cfg.physical_signal = PhysicalSignalConfig(mode="OFF")
            slot_seed = agent_seed(self.seed, i) if self.independent_agent_seeds else int(self.seed)
            rt = PhysicalSystemRuntime(seed=slot_seed, config=cfg)
            rt.technical_id = f"agent_{i}"
            rt.slot_index = i
            rt._defer_manipulator_world = True
            rt._lps_parent_managed = True  # shared-world local signal step runs once in the container
            if i > 0:
                rt.world = self.slots[0].world
                rt.tick = self.slots[0].tick
                rt.body.tick = self.slots[0].body.tick
                rt.internal.tick = self.slots[0].internal.tick
            self.slots.append(rt)
        self.world = self.slots[0].world
        self.config = self.slots[0].config
        from mechanistic_mind.physical_system.procedural_surface_columns import (
            ensure_surface_columns_for_runtime,
        )
        # Shared world geology follows the two-agent world seed, never a per-agent stream.
        ensure_surface_columns_for_runtime(self.world, self.config, experiment_seed=self.seed)
        from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
            ensure_state as ensure_volumetric_occupancy_for_runtime,
        )
        ensure_volumetric_occupancy_for_runtime(self.world, self.config)
        from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
            ensure_state as ensure_occupancy_support_contact_for_runtime,
        )
        ensure_occupancy_support_contact_for_runtime(self.world, self.config)
        from mechanistic_mind.physical_system.volumetric_world_material_separation import (
            ensure_state as ensure_volumetric_separation_for_runtime,
        )
        ensure_volumetric_separation_for_runtime(self.world, self.config)
        from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
            ensure_state as ensure_volumetric_reintegration_for_runtime,
        )
        ensure_volumetric_reintegration_for_runtime(self.world, self.config)
        from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
            ensure_state as ensure_vw5_bridge_for_runtime,
        )
        ensure_vw5_bridge_for_runtime(self.world, self.config)
        from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
            ensure_state as ensure_vw6_vision_for_runtime,
        )
        ensure_vw6_vision_for_runtime(self.world, self.config)
        setattr(self.world, "_physical_system_config", self.config)
        if getattr(self.config, "ses_decomposition_contract", None) is not None:
            from mechanistic_mind.physical_system.ses_decomposition_contract import (
                ensure_ses_decomposition_contract_for_runtime,
            )
            ensure_ses_decomposition_contract_for_runtime(self.world, self.config)
        if getattr(self.config, "ses_runtime_transition_classifier", None) is not None:
            from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
                ensure_ses_runtime_transition_classifier_for_runtime,
            )
            ensure_ses_runtime_transition_classifier_for_runtime(self.world, self.config)
        if getattr(self.config, "radius_aware_face_sweep", None) is not None:
            from mechanistic_mind.physical_system.radius_aware_face_sweep import (
                ensure_radius_aware_face_sweep_for_runtime,
            )
            ensure_radius_aware_face_sweep_for_runtime(self.world, self.config)
        if getattr(self.config, "diagnostic_normal_load_shadow", None) is not None:
            from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
                ensure_diagnostic_normal_load_shadow_for_runtime,
            )
            ensure_diagnostic_normal_load_shadow_for_runtime(self.world, self.config)
        if getattr(self.config, "continuous_gravitational_pe_diagnostic_shadow", None) is not None:
            from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import (
                ensure_continuous_gravitational_pe_diagnostic_shadow_for_runtime,
            )
            ensure_continuous_gravitational_pe_diagnostic_shadow_for_runtime(self.world, self.config)
        self.last_contact = None
        self.last_resource_sim = None
        self.last_signal_receipt = None
        self._pending_sources = []
        if self.signal_enabled:
            ensure_fields(self.world)
        # Lifecycle seam: slot0 built the shared index with only its body; slot1+ rebind the world
        # without rebuilding. After columns/objects exist, rebuild once from the full authoritative
        # entity set before this runtime is exposed (no scientific tick).
        from mechanistic_mind.physical_system.spatial_contents import (
            body_refs_for_runtime,
            rebuild_after_authoritative_entity_change,
        )
        rebuild_after_authoritative_entity_change(
            self.world,
            body_refs_for_runtime(self),
            tick=int(self.tick),
            config=self.config,
            reason="construction",
            generation_policy="fresh",
        )
        self._lps_bind()

    def _lps_bind(self) -> None:
        """Acanthostega local signal: link each shared-world body to its physical body id (sensor seam)."""
        if getattr(getattr(self, "world", None), "local_signal_transport", None) is None:
            return
        from mechanistic_mind.physical_system.local_physical_signal_transport import bind_body_ids
        from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

        bind_body_ids(body_refs_for_runtime(self))

    def spatial_index_consistency(self) -> dict[str, Any]:
        """Researcher/debug-only, read-only: shared index vs authoritative world (all slot bodies)."""
        from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime, spatial_index_consistency

        return spatial_index_consistency(self.world, body_refs_for_runtime(self))

    def construction_audit(self) -> dict[str, Any]:
        """Observer/scientific audit of A vs B construction (not cognition input)."""
        a, b = self.slots[0], self.slots[1]
        return {
            "shared_world": a.world is b.world,
            "shared_cognition_object": a.cognition is b.cognition,
            "shared_body": a.body is b.body,
            "shared_internal": a.internal is b.internal,
            "shared_config_object": a.config is b.config,
            "shared_cognition_config": a.config.cognition is b.config.cognition,
            "agent_seeds": [a.seed, b.seed],
            "world_seed": self.seed,
            "independent_agent_seeds": self.independent_agent_seeds,
            "starts": [list(self.starts[0]), list(self.starts[1])],
            "cognition_enabled": [
                bool(a.config.cognition.cognition_enabled),
                bool(b.config.cognition.cognition_enabled),
            ],
            "prospective_selection": [
                str(a.config.cognition.prospective_selection),
                str(b.config.cognition.prospective_selection),
            ],
            "same_architecture_flags": (
                a.config.cognition.to_dict() == b.config.cognition.to_dict()
                and a.config.discrete_action_work.to_dict() == b.config.discrete_action_work.to_dict()
            ),
        }

    @property
    def tick(self) -> int:
        return int(self.slots[0].tick)

    @property
    def body(self):
        return self.slots[self.selected_index].body

    @property
    def last_selected_action(self):
        return self.slots[self.selected_index].last_selected_action

    @property
    def last_agent_observation(self):
        return self.slots[self.selected_index].last_agent_observation

    @property
    def cognition(self):
        return self.slots[self.selected_index].cognition

    def select_agent(self, index: int) -> int:
        """Observer-only slot selection. Does not enter cognition."""
        n = max(1, len(self.slots))
        self.selected_index = int(index) % n
        return self.selected_index

    def decision_diagnostics(self, slot: int | None = None) -> dict[str, Any]:
        """Read-only WAIT/competition explanation for one or both agents."""
        indices = [int(slot)] if slot is not None else list(range(min(2, len(self.slots))))
        out: dict[str, Any] = {}
        for i in indices:
            rt = self.slots[i]
            sel = rt.cognition.get("last_selection") or {}
            comp = sel.get("competition") or {}
            metrics = rt.cognition.get("metrics") or {}
            counts = dict(metrics.get("action_counts") or {})
            wait_n = int(counts.get("WAIT") or 0)
            move_n = sum(int(v) for k, v in counts.items() if str(k).startswith("MOVE"))
            total = max(1, wait_n + move_n)
            oid = TECHNICAL_IDS[i] if i < len(TECHNICAL_IDS) else f"agent_{i}"
            out[oid] = {
                "selected_action": rt.last_selected_action,
                "selection_source": sel.get("source"),
                "selection_reason": comp.get("selection_reason") or sel.get("selection_rule"),
                "outcome_class": comp.get("outcome_class"),
                "supported_actions": comp.get("supported_actions"),
                "unsupported_actions": comp.get("unsupported_actions"),
                "tie_resolution": comp.get("tie_resolution"),
                "selected_scenario": comp.get("selected_scenario"),
                "scenario_groups": sel.get("scenario_groups"),
                "action_counts": counts,
                "wait_rate": wait_n / total,
                "move_rate": move_n / total,
                "prospective_compositions": metrics.get("prospective_compositions"),
                "agent_seed": rt.seed,
            }
        return out

    def observer_agent_summaries(self) -> list[dict[str, Any]]:
        out = []
        for i, rt in enumerate(self.slots):
            ras = getattr(rt.body, "R_A_site", None)
            rbs = getattr(rt.body, "R_B_site", None)
            sel = rt.cognition.get("last_selection") or {}
            comp = sel.get("competition") or {}
            metrics = rt.cognition.get("metrics") or {}
            counts = dict(metrics.get("action_counts") or {})
            wait_n = int(counts.get("WAIT") or 0)
            move_n = sum(int(v) for k, v in counts.items() if str(k).startswith("MOVE"))
            st = self._agent_stats[i] if i < len(self._agent_stats) else _empty_agent_stats()
            unique = st.get("unique_cells") or set()
            is_exp = (
                self.experimenter_slot is not None
                and i == int(self.experimenter_slot)
            )
            from mechanistic_mind.ui.psy_observer_web.undercover_identity import (
                slot_agent_body_ids,
            )
            oid, bid = slot_agent_body_ids(i, experimenter_slot=self.experimenter_slot)
            row = {
                "observer_id": oid,
                "agent_id": oid,
                "body_id": bid,
                "x": float(rt.body.x),
                "y": float(rt.body.y),
                "theta": float(getattr(rt.body, "theta", 0.0) or 0.0),
                "vx": float(rt.body.vx),
                "vy": float(rt.body.vy),
                "work": float(getattr(rt.body, "mechanical_work_reservoir", 0.0) or 0.0),
                "body_A": float(np.sum(ras)) if ras is not None else 0.0,
                "body_B": float(np.sum(rbs)) if rbs is not None else 0.0,
                "selected_action": rt.last_selected_action,
                "selection_source": sel.get("source"),
                "selection_reason": comp.get("selection_reason"),
                "supported_actions": comp.get("supported_actions"),
                "unsupported_actions": comp.get("unsupported_actions"),
                "action_counts": counts,
                "wait_count": wait_n,
                "move_count": move_n,
                "wait_rate": wait_n / max(1, wait_n + move_n),
                "move_rate": move_n / max(1, wait_n + move_n),
                "prospective_compositions": metrics.get("prospective_compositions"),
                "prediction_count": metrics.get("prediction_count"),
                "distance_travelled": float(st.get("distance_travelled") or 0.0),
                "unique_cells_visited": len(unique) if isinstance(unique, set) else int(unique),
                "collision_count": int(st.get("collision_ticks") or 0),
                "cognition_ticks": int(st.get("cognition_ticks") or 0),
                "agent_seed": int(rt.seed),
                "tick": int(rt.tick),
            }
            # Observer-only flags — never copied into agent observations.
            if is_exp:
                row["observer_experimenter"] = True
                row["observer_undercover"] = True
                row["observer_label"] = "UNDERCOVER"
                row["action_authority"] = "EXPERIMENTER"
            out.append(row)
        return out

    def foreign_bodies_for(self, observer_index: int) -> list[tuple[Any, Any]]:
        """All physical bodies except the observer — one shared vision path per slot."""
        n = len(self.slots)
        if n <= 0:
            return []
        oi = int(observer_index) % n
        return [
            (self.slots[j].body, self.slots[j].config.body)
            for j in range(n)
            if j != oi
        ]

    def agent_observation(self, foreign_bodies=None):
        i = int(self.selected_index)
        fb = foreign_bodies if foreign_bodies is not None else self.foreign_bodies_for(i)
        return self.slots[i].agent_observation(foreign_bodies=fb)

    def observation_views(self, foreign_bodies=None):
        i = int(self.selected_index)
        fb = foreign_bodies if foreign_bodies is not None else self.foreign_bodies_for(i)
        return self.slots[i].observation_views(foreign_bodies=fb)

    def cognitive_view(self):
        return self.slots[self.selected_index].cognitive_view()

    def cognitive_view_cache_stats(self) -> dict:
        builds = hits = 0
        for slot in self.slots:
            st = slot.cognitive_view_cache_stats() if hasattr(slot, "cognitive_view_cache_stats") else {}
            builds += int(st.get("builds") or 0)
            hits += int(st.get("hits") or 0)
        return {"builds": builds, "hits": hits, "agents": len(self.slots)}

    def reset_cognitive_view_cache_stats(self) -> None:
        for slot in self.slots:
            if hasattr(slot, "reset_cognitive_view_cache_stats"):
                slot.reset_cognitive_view_cache_stats()

    def mechanisms(self):
        """Mechanism snapshot. Flags are kept identical across slots (see set_mechanism)."""
        return self.slots[0].mechanisms()

    def mechanism_snapshot(self):
        return self.mechanisms()

    def model_identity(self) -> dict[str, Any]:
        slot = self.slots[self.selected_index] if self.slots else None
        if slot is not None:
            return slot.model_identity()
        from mechanistic_mind.model.lines import identity_for_config

        return identity_for_config(getattr(self, "config", None), seed=self.seed, tick=self.tick)

    def set_psc_motor_resolution(self, mode: str) -> dict[str, Any]:
        """Apply motor-resolution mode to all agent slots (no resets)."""
        results = []
        for slot in self.slots:
            results.append(slot.set_psc_motor_resolution(mode))
        # Keep shared config view aligned with slot 0
        if self.slots:
            self.config = self.slots[0].config
        return {
            "accepted": all(r.get("accepted") for r in results),
            "agents": results,
            "psc_motor_resolution": (results[0].get("new") if results else mode),
            "history_reset": False,
            "cognition_reset": False,
            "smc_reset": False,
            "body_reset": False,
        }

    def set_mechanism(self, mechanism_id: str, enabled: bool) -> dict[str, Any]:
        """Apply experiment toggles to every agent slot.

        EXPERIMENT UI switches are global ("enabled for every applicable agent").
        Without this override, ``__getattr__`` would route to selected_index only and
        desync agent_0 vs agent_1 mechanism configuration.
        """
        snap = None
        for rt in self.slots:
            snap = rt.set_mechanism(mechanism_id, bool(enabled))
        self.config = self.slots[0].config
        # Keep TwoAgentRuntime's shared-world signal bridge aligned with the
        # EXPERIMENT toggle. Config.mode alone is not enough: SIGNAL A/B grids
        # must be allocated for Observer discovery, and signal_enabled must
        # match so reset()/construction stay consistent.
        if mechanism_id == "experimental_physical_signal":
            on = bool(enabled)
            self.signal_enabled = on
            if on:
                ensure_fields(self.world)
            else:
                clear_fields(self.world)
        return snap if snap is not None else self.mechanisms()

    def set_vision_radius(self, radius: int) -> dict[str, Any]:
        """Apply vision Moore radius to every agent slot (global Observer control)."""
        snap = None
        for rt in self.slots:
            snap = rt.set_vision_radius(radius)
        self.config = self.slots[0].config
        return snap if snap is not None else {"accepted": False, "reason": "no slots"}

    def set_visual_surface_discrimination(self, mode: str) -> dict[str, Any]:
        snap = None
        for rt in self.slots:
            snap = rt.set_visual_surface_discrimination(mode)
        self.config = self.slots[0].config
        return snap if snap is not None else {"accepted": False, "reason": "no slots"}

    def set_optical_mapping(self, mode: str, *, reinstall: bool = True) -> dict[str, Any]:
        snap = None
        for i, rt in enumerate(self.slots):
            snap = rt.set_optical_mapping(mode, reinstall=(reinstall and i == 0))
            if i > 0:
                nfe = getattr(rt.config, "near_field_exteroception", None)
                if nfe is not None and snap:
                    nfe.optical_mapping = snap.get("new") or nfe.optical_mapping
        self.config = self.slots[0].config
        return snap if snap is not None else {"accepted": False, "reason": "no slots"}

    def set_spatial_vision(self, mode: str, *, n_sectors: int | None = None) -> dict[str, Any]:
        snap = None
        for rt in self.slots:
            snap = rt.set_spatial_vision(mode, n_sectors=n_sectors)
        self.config = self.slots[0].config
        return snap if snap is not None else {"accepted": False, "reason": "no slots"}

    def set_psc_off_ticks(self, value: int | None) -> dict[str, Any]:
        snap = None
        for rt in self.slots:
            snap = rt.set_psc_off_ticks(value)
        self.config = self.slots[0].config
        return snap if snap is not None else {"accepted": False, "reason": "no slots"}

    def set_ablations(self, **flags: bool) -> None:
        """Apply ablations to every agent slot (same rationale as set_mechanism)."""
        for rt in self.slots:
            rt.set_ablations(**flags)
        self.config = self.slots[0].config

    def mechanism_parity_audit(self) -> dict[str, Any]:
        """Observer/diagnostic: compare enabled mechanism sets across slots."""
        from mechanistic_mind.physical_system.mechanism_registry import mechanism_snapshot

        snaps = [mechanism_snapshot(rt.config) for rt in self.slots]
        by_id = []
        ids = [m["id"] for m in snaps[0].get("mechanisms", [])] if snaps else []
        mismatches: list[dict[str, Any]] = []
        for mid in ids:
            states = []
            for snap in snaps:
                item = next((m for m in snap.get("mechanisms", []) if m.get("id") == mid), None)
                states.append(None if item is None else item.get("enabled"))
            row = {"id": mid, "enabled": states, "parity": len(set(states)) <= 1}
            by_id.append(row)
            if not row["parity"]:
                mismatches.append(row)
        cog = [rt.config.cognition.to_dict() for rt in self.slots]
        return {
            "slot_count": len(self.slots),
            "cognition_config_equal": all(c == cog[0] for c in cog),
            "mechanism_mismatches": mismatches,
            "mechanisms": by_id,
            "intentional_identity_diffs": {
                "agent_seeds": [rt.seed for rt in self.slots],
                "starts": [
                    list(self.starts[i]) if i < len(self.starts) else None
                    for i in range(len(self.slots))
                ],
                "start_xy": [
                    (rt.config.body.start_x, rt.config.body.start_y) for rt in self.slots
                ],
            },
        }

    def __getattr__(self, name: str):
        if name.startswith("_") or not self.slots:
            raise AttributeError(name)
        return getattr(self.slots[self.selected_index], name)

    def observations(self) -> list[dict[str, float]]:
        out = []
        self._lps_bind()
        for i, rt in enumerate(self.slots):
            obs = rt.agent_observation(foreign_bodies=self.foreign_bodies_for(i))
            hits = audit_cognition_payload(obs)
            if hits:
                raise RuntimeError(f"cognition observation leaked: {hits}")
            for tok in ("agent_0", "agent_1", "other agent", "enemy", "friend", "FIELD_A_FROM", "source_agent"):
                if tok in repr(obs):
                    raise RuntimeError(f"technical identity leaked into observation: {tok}")
            out.append(obs)
        return out

    def step(self, n: int = 1) -> None:
        for _ in range(max(1, int(n))):
            self._step_once()
            for rt in self.slots:
                rt._maybe_auto_enable_psc()

    def _record_stats_after_tick(self) -> None:
        contact = bool((self.last_contact or {}).get("contact"))
        for i, rt in enumerate(self.slots):
            st = self._agent_stats[i]
            st["ticks"] = int(st.get("ticks") or 0) + 1
            act = rt.last_selected_action
            if act is not None:
                counts = st.setdefault("action_counts", {})
                key = str(act)
                counts[key] = int(counts.get(key) or 0) + 1
                if act == "WAIT":
                    st["wait_count"] = int(st.get("wait_count") or 0) + 1
                elif str(act).startswith("MOVE"):
                    st["move_count"] = int(st.get("move_count") or 0) + 1
            if rt.config.cognition.cognition_enabled:
                st["cognition_ticks"] = int(st.get("cognition_ticks") or 0) + 1
            xy = (float(rt.body.x), float(rt.body.y))
            prev = self._prev_xy[i]
            if prev is not None:
                w = int(self.world.T.shape[1])
                h = int(self.world.T.shape[0])
                dx = _wrap_delta_1d(prev[0], xy[0], w)
                dy = _wrap_delta_1d(prev[1], xy[1], h)
                st["distance_travelled"] = float(st.get("distance_travelled") or 0.0) + (
                    abs(dx) + abs(dy)
                )
            self._prev_xy[i] = xy
            cells = st.setdefault("unique_cells", set())
            if isinstance(cells, set):
                w = int(self.world.T.shape[1])
                h = int(self.world.T.shape[0])
                cells.add((int(xy[0]) % w, int(xy[1]) % h))
            if contact:
                st["collision_ticks"] = int(st.get("collision_ticks") or 0) + 1
            sel = rt.cognition.get("last_selection") or {}
            st["last_competition"] = {
                "action": rt.last_selected_action,
                "source": sel.get("source"),
                "reason": (sel.get("competition") or {}).get("selection_reason"),
                "supported": (sel.get("competition") or {}).get("supported_actions"),
            }

    def _step_once(self) -> None:
        from mechanistic_mind.research.tick_profiler import span

        n = len(self.slots)
        order = self.process_order if len(self.process_order) == n else tuple(range(n))
        with span("observation"):
            obs = self.observations()
        with span("cognition_motor"):
            for i in order:
                with span(f"begin_tick_agent_{i}"):
                    self.slots[i].begin_tick(observation=obs[i])
        with span("world_physics"):
            step_planet(self.world, self.slots[0].config.planet, seed=self.seed)
        with span("body_finish"):
            for i in order:
                self.slots[i].finish_tick(skip_planet=True, skip_resources=True)
        w = int(self.world.T.shape[1])
        h = int(self.world.T.shape[0])
        # Pairwise soft contact for all bodies (including optional experimenter slot).
        self.last_contacts = []
        # Acanthostega Audio B (contact acoustics): read-only pre-resolution pose/velocity snapshot.
        pca_state = getattr(self.world, "contact_acoustic_state", None)
        pca_rows: list[dict[str, Any]] = []
        pca_pre = None
        pca_ids: list[str] = []
        if pca_state is not None:
            from mechanistic_mind.physical_system.physical_contact_acoustic_emission import capture_pre_contact
            from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

            pca_refs = body_refs_for_runtime(self)
            pca_ids = [str(r[0]) for r in pca_refs]
            pca_pre = capture_pre_contact(pca_refs)
        with span("contact_push"):
            for ia in range(n):
                for ib in range(ia + 1, n):
                    _bb_enabled = bool(self.contact_enabled)
                    from mechanistic_mind.physical_system.flat_ground_gravity import (
                        flat_ground_gravity_is_active as _fgg_bb,
                        vertical_overlap_at_endpoint as _v_overlap_bb,
                    )
                    if _bb_enabled and _fgg_bb(self.slots[0].config):
                        if not _v_overlap_bb(
                            self.slots[ia].body,
                            self.slots[ib].body,
                            kind_a="body",
                            kind_b="body",
                            config=self.slots[0].config,
                        ):
                            _bb_enabled = False
                    receipt = resolve_soft_contact(
                        self.slots[ia].body,
                        self.slots[ib].body,
                        self.slots[ia].config.body,
                        self.slots[ib].config.body,
                        width=w,
                        height=h,
                        enabled=_bb_enabled,
                    )
                    if (not _bb_enabled) and bool(self.contact_enabled) and _fgg_bb(self.slots[0].config):
                        receipt = dict(receipt or {})
                        receipt["vertical_filter"] = "REJECT"
                        receipt["vertical_separation_reason"] = "VERTICAL_SEPARATION"
                        receipt["contact"] = False
                    push_receipt = apply_push_through_contact(
                        self.slots[ia].body,
                        self.slots[ib].body,
                        self.slots[ia].config.body,
                        self.slots[ib].config.body,
                        contact=bool(receipt and receipt.get("contact")),
                        push_cfg=self.slots[ia].config.physical_push,
                        width=w,
                        height=h,
                    )
                    if receipt is not None:
                        receipt["push"] = push_receipt
                        receipt.setdefault("contact_entity_a_kind", "BODY")
                        receipt.setdefault("contact_entity_a_id", f"body-{ia}")
                        receipt.setdefault("contact_entity_b_kind", "BODY")
                        receipt.setdefault("contact_entity_b_id", f"body-{ib}")
                        receipt["pair"] = (ia, ib)
                    if push_receipt.get("push_applied"):
                        for slot_i in (ia, ib):
                            self.slots[slot_i].last_push_meta = push_receipt
                            self.slots[slot_i].structured_events.emit(
                                "PUSH_FORCE_APPLIED",
                                tick=int(self.tick),
                                evidence={
                                    "pair": [ia, ib],
                                    "pusher": push_receipt.get("pusher"),
                                    "causally_linked": True,
                                    "impulse_a": push_receipt.get("impulse_a"),
                                    "impulse_b": push_receipt.get("impulse_b"),
                                    "semantics": push_receipt.get("semantics"),
                                },
                            )
                    elif push_receipt.get("push_without_contact"):
                        for slot_i in (ia, ib):
                            self.slots[slot_i].structured_events.emit(
                                "PUSH_NO_CONTACT",
                                tick=int(self.tick),
                                evidence={"pair": [ia, ib], "force_transferred": False},
                            )
                    self.last_contacts.append(receipt)
                    if pca_state is not None and receipt is not None and ia < len(pca_ids) and ib < len(pca_ids):
                        pca_rows.append({
                            "a_id": pca_ids[ia], "b_id": pca_ids[ib],
                            "mass_a": float(self.slots[ia].config.body.mass),
                            "mass_b": float(self.slots[ib].config.body.mass),
                            "contact_receipt": receipt, "push_receipt": push_receipt,
                            "body_a": self.slots[ia].body, "body_b": self.slots[ib].body,
                        })
            if pca_state is not None:
                # One pass after the whole contact/PUSH loop: measured new impulse -> physical emission
                # for emission tick te = tick - 1 (the tick being resolved); transport step follows below.
                from mechanistic_mind.physical_system.physical_contact_acoustic_emission import process_contact_pairs

                self.last_contact_acoustic = process_contact_pairs(
                    self.world, self.slots[0].config, pca_rows,
                    emission_tick=int(self.tick) - 1, pre_contact=pca_pre,
                )
            # Preserve last_contact as agent_0↔agent_1 (or first overlapping pair).
            self.last_contact = None
            if n >= 2:
                self.last_contact = self.last_contacts[0] if self.last_contacts else None
                for r in self.last_contacts:
                    if r and r.get("contact"):
                        self.last_contact = r
                        break
        from mechanistic_mind.physical_system.physical_manipulator import (
            resolve_shared_world_manipulators,
            world_manipulators_active,
        )
        if self.slots and world_manipulators_active(self.slots[0].config):
            done_tick = max(0, int(self.slots[0].tick) - 1)
            resolve_shared_world_manipulators(self.slots, self.world, tick=done_tick)
        # Agent effector_z (deferred path): after shared manipulators, before ETC.
        if self.slots:
            done_tick = max(0, int(self.slots[0].tick) - 1)
            for slot in self.slots:
                if bool(getattr(slot, "_defer_manipulator_world", False)):
                    slot._apply_agent_effector_relative_z_from_motor(actuation_tick=done_tick)
        if self.slots:
            from mechanistic_mind.physical_system.spatial_contents import (
                body_refs_for_runtime,
                multi_content_spatial_index_is_active,
                reconcile_contents,
            )
            if multi_content_spatial_index_is_active(self.slots[0].config):
                reconcile_contents(
                    self.world,
                    body_refs_for_runtime(self),
                    tick=int(self.tick),
                    reason="contact_and_manipulator",
                    config=self.slots[0].config,
                )
            from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
                body_object_contact_is_active,
                detect_body_resource_object_contacts,
            )
            if body_object_contact_is_active(self.slots[0].config):
                # Same scientific tick as shared manipulators (slot.tick already advanced).
                boc_tick = max(0, int(self.slots[0].tick) - 1)
                detect_body_resource_object_contacts(
                    self.world,
                    body_refs_for_runtime(self),
                    tick=boc_tick,
                    config=self.slots[0].config,
                )
                from mechanistic_mind.physical_system.body_resource_object_contact_impulse import (
                    body_object_impulse_is_active,
                    apply_body_object_contact_impulse,
                )
                if body_object_impulse_is_active(self.slots[0].config):
                    body_triples = []
                    for bid, b in body_refs_for_runtime(self):
                        # Match slot config by body identity / order
                        body_cfg = self.slots[0].config.body
                        for slot in self.slots:
                            if slot.body is b:
                                body_cfg = slot.config.body
                                break
                        body_triples.append((bid, b, body_cfg))
                    apply_body_object_contact_impulse(
                        self.world,
                        body_triples,
                        tick=boc_tick,
                        config=self.slots[0].config,
                    )
                    from mechanistic_mind.physical_system.body_resource_object_impact_acoustic_emission import (
                        body_object_impact_acoustics_is_active,
                        process_body_object_impact_acoustics,
                    )
                    if body_object_impact_acoustics_is_active(self.slots[0].config):
                        process_body_object_impact_acoustics(
                            self.world,
                            self.slots[0].config,
                            emission_tick=boc_tick,
                        )
                from mechanistic_mind.physical_system.physical_resource_object_pair_contact import (
                    resource_object_pair_contact_is_active,
                    detect_resource_object_pair_contacts,
                )
                if resource_object_pair_contact_is_active(self.slots[0].config):
                    detect_resource_object_pair_contacts(
                        self.world,
                        tick=boc_tick,
                        config=self.slots[0].config,
                    )
                    from mechanistic_mind.physical_system.resource_object_pair_contact_impulse import (
                        resource_object_pair_impulse_is_active,
                        apply_resource_object_pair_contact_impulse,
                    )
                    if resource_object_pair_impulse_is_active(self.slots[0].config):
                        apply_resource_object_pair_contact_impulse(
                            self.world,
                            tick=boc_tick,
                            config=self.slots[0].config,
                            bodies=body_refs_for_runtime(self),
                        )
                        from mechanistic_mind.physical_system.resource_object_pair_impact_acoustic_emission import (
                            resource_object_pair_impact_acoustics_is_active,
                            process_resource_object_pair_impact_acoustics,
                        )
                        if resource_object_pair_impact_acoustics_is_active(self.slots[0].config):
                            process_resource_object_pair_impact_acoustics(
                                self.world,
                                self.slots[0].config,
                                emission_tick=boc_tick,
                            )
                from mechanistic_mind.physical_system.held_resource_object_foreign_body_contact import (
                    held_foreign_body_contact_is_active,
                    detect_held_resource_object_foreign_body_contacts,
                )
                if held_foreign_body_contact_is_active(self.slots[0].config):
                    detect_held_resource_object_foreign_body_contacts(
                        self.world,
                        body_refs_for_runtime(self),
                        tick=boc_tick,
                        config=self.slots[0].config,
                    )
                    from mechanistic_mind.physical_system.held_resource_object_translational_impulse_mediation import (
                        held_translational_impulse_is_active,
                        apply_held_resource_object_translational_impulse_mediation,
                    )
                    if held_translational_impulse_is_active(self.slots[0].config):
                        body_triples = []
                        for bid, b in body_refs_for_runtime(self):
                            body_cfg = self.slots[0].config.body
                            for slot in self.slots:
                                if slot.body is b:
                                    body_cfg = slot.config.body
                                    break
                            body_triples.append((bid, b, body_cfg))
                        apply_held_resource_object_translational_impulse_mediation(
                            self.world,
                            body_triples,
                            tick=boc_tick,
                            config=self.slots[0].config,
                        )
            from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
                detect_effector_terrain_contacts,
                effector_terrain_contact_geometry_is_active,
            )
            if effector_terrain_contact_geometry_is_active(self.slots[0].config):
                etc_tick = max(0, int(self.slots[0].tick) - 1)
                holders = []
                for bid, b in body_refs_for_runtime(self):
                    slot_cfg = self.slots[0].config
                    slot_rt = self.slots[0]
                    for slot in self.slots:
                        if slot.body is b:
                            slot_cfg = slot.config
                            slot_rt = slot
                            break
                    holders.append(
                        {"body_id": bid, "body": b, "config": slot_cfg, "runtime": slot_rt}
                    )
                detect_effector_terrain_contacts(
                    self.world,
                    holders,
                    tick=etc_tick,
                    config=self.slots[0].config,
                )
            from mechanistic_mind.physical_system.held_resource_object_terrain_contact_geometry import (
                detect_held_resource_object_terrain_contacts,
                held_resource_object_terrain_contact_geometry_is_active,
            )
            if held_resource_object_terrain_contact_geometry_is_active(self.slots[0].config):
                hotc_tick = max(0, int(self.slots[0].tick) - 1)
                holders_hotc = []
                for bid, b in body_refs_for_runtime(self):
                    slot_cfg = self.slots[0].config
                    slot_rt = self.slots[0]
                    for slot in self.slots:
                        if slot.body is b:
                            slot_cfg = slot.config
                            slot_rt = slot
                            break
                    holders_hotc.append(
                        {"body_id": bid, "body": b, "config": slot_cfg, "runtime": slot_rt}
                    )
                detect_held_resource_object_terrain_contacts(
                    self.world,
                    holders_hotc,
                    tick=hotc_tick,
                    config=self.slots[0].config,
                )
        bodies = [s.body for s in self.slots]
        body_cfgs = [s.config.body for s in self.slots]
        with span("resources"):
            self.last_resource_sim = simultaneous_complementary_resources(
                bodies,
                self.world,
                body_cfgs,
                self.slots[0].config.complementary_resources,
                self.slots[0].config.deformation_work,
                receipt_tick=int(self.tick),
            )
            for i, rt in enumerate(self.slots):
                if self.last_resource_sim and i < len(self.last_resource_sim):
                    rt.last_complementary_ledger = self.last_resource_sim[i]
        extra = list(self._pending_sources)
        self._pending_sources = []
        h, w = int(self.world.T.shape[0]), int(self.world.T.shape[1])
        for src in extra:
            if "slot" in src and "cells" not in src:
                i = int(src["slot"])
                if 0 <= i < n:
                    src["cells"] = _site_cells(self.slots[i].body, self.slots[i].config.body, w, h)
        with span("signals"):
            sig_cfg = self.slots[0].config.physical_signal
            if self.signal_enabled or sig_cfg.enabled:
                self.last_signal_receipt = step_physical_signals(
                    self.world,
                    bodies,
                    body_cfgs,
                    sig_cfg,
                    contact=self.last_contact,
                    extra_sources=extra,
                    receipt_tick=int(self.tick),
                )
                self._emit_signal_events()
            else:
                self.last_signal_receipt = None
            # Oscillatory banded signaling (Option B) — shared world, all bodies.
            osc_cfg = getattr(self.slots[0].config, "oscillatory_signaling", None)
            from mechanistic_mind.physical_system.vertical_impact_acoustic_emission import (
                process_vertical_impact_acoustic_emission,
                vertical_impact_acoustic_emission_is_active,
            )
            if vertical_impact_acoustic_emission_is_active(self.slots[0].config):
                # Shared world: consume landing responses once before sole LPS step.
                via_tick = max(0, int(self.slots[0].tick) - 1)
                process_vertical_impact_acoustic_emission(
                    self.world,
                    self.slots[0].config,
                    emission_tick=via_tick,
                )
            if getattr(self.world, "local_signal_transport", None) is not None:
                # Acanthostega LOCAL PHYSICAL SIGNAL TRANSPORT: one deterministic, process-order-free
                # end-of-tick step for all bodies (emission at pose -> finite-speed wavefront).
                from mechanistic_mind.physical_system.local_physical_signal_transport import step_end_of_tick
                from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime
                from mechanistic_mind.ui.psy_observer_web.undercover_identity import slot_agent_body_ids

                exp_slot = getattr(self, "experimenter_slot", None)
                intervention_ids = (
                    (slot_agent_body_ids(int(exp_slot), experimenter_slot=exp_slot)[1],)
                    if exp_slot is not None else ()
                )
                lps = step_end_of_tick(
                    self.world,
                    self.slots[0].config,
                    body_refs_for_runtime(self),
                    tick_now=int(self.tick),
                    articulated_head=bool(getattr(self.slots[0].config.articulated_head, "enabled", False)),
                    intervention_body_ids=intervention_ids,
                )
                # Read-only scientific stream over committed emissions (no LPS re-step).
                from mechanistic_mind.physical_system.authoritative_physical_acoustic_stream_contract import (
                    sync_acoustic_stream,
                )

                sync_acoustic_stream(self.world, scientific_tick=int(self.tick))
                from mechanistic_mind.physical_system.observer_acoustic_probe import (
                    sample_observer_acoustic_probe,
                )

                sample_observer_acoustic_probe(self.world, scientific_tick=int(self.tick))
                osc_meta = {
                    "enabled": True,
                    "transport": "LOCAL_PHYSICAL_SIGNAL_TRANSPORT_V1",
                    "emissions": len(lps.get("emissions") or []),
                    "receptions": len(lps.get("receptions") or []),
                }
                self.last_osc_meta = osc_meta
                for rt in self.slots:
                    rt.last_osc_meta = osc_meta
                    rt.world = self.world
            elif osc_cfg is not None and osc_cfg.enabled:
                from mechanistic_mind.physical_system.oscillatory_signaling import (
                    ensure_osc_fields,
                    step_oscillatory_signaling,
                )
                ensure_osc_fields(self.world, osc_cfg)
                head_on = bool(getattr(self.slots[0].config.articulated_head, "enabled", False))
                osc_meta = step_oscillatory_signaling(
                    self.world,
                    bodies,
                    osc_cfg,
                    tick=int(self.tick),
                    articulated_head=head_on,
                    body_ids=[f"agent_{i}" for i in range(n)],
                    slots=list(range(n)),
                )
                self.last_osc_meta = osc_meta
                for rt in self.slots:
                    rt.last_osc_meta = osc_meta
                    rt.world = self.world
            else:
                self.last_osc_meta = {"enabled": False}
        for rt in self.slots:
            rt.world = self.world
        self._record_stats_after_tick()

    def inject_source(
        self,
        *,
        channel: str = "A",
        amplitude: float = 1.0,
        slot: int | None = None,
        iy: int | None = None,
        ix: int | None = None,
        cells: list[tuple[int, int]] | None = None,
        trigger: str = "environmental",
        observer_source_id: str | None = None,
    ) -> None:
        """Queue a physical deposit for the end of the next tick. Not a selected EMIT action.

        Prefer ``cells`` or ``(iy, ix)`` for EXTERNAL_EXPERIMENTAL_INTERVENTION so the
        deposit uses the shared FIELD path without body-slot emitter identity.
        """
        src: dict[str, Any] = {
            "channel": str(channel).upper(),
            "amplitude": float(amplitude),
            "trigger": trigger,
            "observer_source_id": observer_source_id
            or ("environment" if slot is None else f"agent_{int(slot)}"),
        }
        if cells is not None:
            src["cells"] = [(int(c[0]), int(c[1])) for c in cells]
        elif slot is not None:
            src["slot"] = int(slot)
        else:
            src["iy"] = int(iy if iy is not None else 0)
            src["ix"] = int(ix if ix is not None else 0)
        self._pending_sources.append(src)

    def local_signal(self, slot: int, channel: str) -> float:
        rt = self.slots[int(slot)]
        h, w = self.world.T.shape
        cells = _site_cells(rt.body, rt.config.body, w, h)
        return sample_local(self.world, cells, str(channel).upper())

    def _emit_signal_events(self) -> None:
        rec = self.last_signal_receipt or {}
        tick = int(self.tick)
        sources = list(rec.get("sources") or [])
        if rec.get("emitted"):
            for src in sources:
                slot_i = src.get("slot")
                if slot_i is None and str(src.get("observer_source_id") or "").startswith("agent_"):
                    try:
                        slot_i = int(str(src["observer_source_id"]).split("_", 1)[1])
                    except Exception:
                        slot_i = None
                emitter_id = src.get("emitter_agent_id")
                body_id = src.get("emitter_body_id")
                if emitter_id in (None, "", "UNKNOWN") and slot_i is not None:
                    emitter_id = f"agent_{int(slot_i)}"
                if body_id in (None, "", "UNKNOWN") and slot_i is not None:
                    body_id = f"body-{int(slot_i)}"
                if emitter_id in (None, ""):
                    emitter_id = "UNKNOWN"
                if body_id in (None, ""):
                    body_id = "UNKNOWN"
                evidence = {k: v for k, v in src.items()}
                # Keep cells for Observer specimen capture (SIGINT-03); never fed to cognition.
                evidence["emitter_agent_id"] = emitter_id
                evidence["emitter_body_id"] = body_id
                evidence["body_id"] = body_id
                evidence.setdefault("channel", evidence.get("field") or evidence.get("channel"))
                evidence.setdefault("origin_kind", evidence.get("origin_kind") or "NOT_RECORDED")
                evidence.setdefault("origin_id", evidence.get("origin_id") or "NOT_RECORDED")
                evidence.setdefault(
                    "observer_source_id",
                    src.get("observer_source_id") or (f"agent_{int(slot_i)}" if slot_i is not None else "NOT_RECORDED"),
                )
                evidence["note"] = (
                    "PHYSICAL_SIGNAL_EMITTED — physical field deposit; not communication. "
                    "observer_source_id is instrumentation stream, not emitter identity."
                )
                # Record on the emitter's buffer only (no cross-buffer identity rewrite).
                if slot_i is not None and 0 <= int(slot_i) < len(self.slots):
                    targets = [self.slots[int(slot_i)]]
                else:
                    # Environmental / unscoped deposit: record once on slot 0 buffer.
                    targets = [self.slots[0]] if self.slots else []
                for rt in targets:
                    rt.structured_events.emit(
                        "PHYSICAL_SIGNAL_EMITTED",
                        tick=tick,
                        evidence=evidence,
                    )
        floor = float((self.slots[0].config.physical_signal.floor if self.slots else 1e-4))
        if not self.slots[0].config.physical_signal.perception_enabled:
            return
        for i, rt in enumerate(self.slots):
            a = self.local_signal(i, "A")
            b = self.local_signal(i, "B")
            if a > floor or b > floor:
                # Continuum field: residual + superposition → unique emitter not guaranteed.
                contrib: list[dict[str, Any]] = []
                for src in sources:
                    ch = str(src.get("channel") or "").upper()
                    if ch == "A" and a > floor:
                        contrib.append(src)
                    elif ch == "B" and b > floor:
                        contrib.append(src)
                channels_hit = []
                if a > floor:
                    channels_hit.append("A")
                if b > floor:
                    channels_hit.append("B")
                by_channel = {ch: [s for s in contrib if str(s.get("channel") or "").upper() == ch] for ch in channels_hit}
                multi = any(len(v) > 1 for v in by_channel.values()) or len(channels_hit) > 1 and len(contrib) > 1
                if not contrib:
                    attribution = "NOT_UNIQUELY_ATTRIBUTABLE"
                    source_note = "FIELD_RESIDUAL_OR_PRIOR_TICKS"
                elif multi:
                    attribution = "MIXED"
                    source_note = "MULTIPLE_SAME_TICK_DEPOSITS"
                else:
                    # Single same-tick deposit exists, but residual field still mixes contributions.
                    attribution = "NOT_UNIQUELY_ATTRIBUTABLE"
                    source_note = "CONTINUUM_FIELD_SUPERPOSITION"
                evidence = {
                    "local.FIELD_A": a,
                    "local.FIELD_B": b,
                    "receiver_agent_id": f"agent_{i}",
                    "receiver_body_id": f"body-{i}",
                    "body_id": f"body-{i}",
                    "observer_source_id": f"agent_{i}",
                    "observer_receiver_id": f"agent_{i}",
                    "source_attribution": attribution,
                    "source_agent_id": "UNKNOWN",
                    "source_body_id": "UNKNOWN",
                    "source_origin_kind": "NOT_RECORDED",
                    "source_origin_id": "NOT_RECORDED",
                    "source": source_note,
                    "contributing_emissions_this_tick": [
                        {
                            "emission_id": s.get("emission_id"),
                            "channel": s.get("channel"),
                            "trigger": s.get("trigger"),
                            "emitter_agent_id": s.get("emitter_agent_id"),
                            "emitter_body_id": s.get("emitter_body_id"),
                            "origin_kind": s.get("origin_kind"),
                            "origin_id": s.get("origin_id"),
                            "originating_tick": tick,
                        }
                        for s in contrib
                    ],
                    "causal_parent_ids": [s.get("emission_id") for s in contrib if s.get("emission_id")],
                    "note": (
                        "PHYSICAL_SIGNAL_RECEIVED — local field sample; not communication. "
                        "Unique emitter not attributable under continuum superposition."
                    ),
                }
                rt.structured_events.emit(
                    "PHYSICAL_SIGNAL_RECEIVED",
                    tick=tick,
                    evidence=evidence,
                )

    def snapshot(self, *, persist: bool = False) -> dict[str, Any]:
        agents = []
        for i, slot in enumerate(self.slots):
            snap = slot.snapshot(persist=persist)
            if i > 0:
                snap.pop("world", None)
            agents.append(snap)
        ident = self.model_identity()
        return {
            "schema": "mm.physical_system.two_agent.snapshot.v1",
            "experimental": True,
            "promoted": False,
            "model": ident,
            "runtime_version": ident.get("runtime_version") or getattr(self.config, "runtime_version", None),
            "tick": self.tick,
            "seed": self.seed,
            "independent_agent_seeds": self.independent_agent_seeds,
            "agent_seeds": [s.seed for s in self.slots],
            "starts": [
                list(self.starts[i]) if i < len(self.starts) else (
                    list(self.starts[0]) if self.starts else [0, 0]
                )
                for i in range(max(2, len(self.starts)))
            ],
            "contact_enabled": self.contact_enabled,
            "field_coupling_enabled": self.field_coupling_enabled,
            "signal_enabled": self.signal_enabled,
            "process_order": list(self.process_order),
            "world": agents[0]["world"],
            "agents": agents,
            "experimenter_slot": self.experimenter_slot,
            "experimenter_intervention": self.experimenter_slot is not None,
        }

    @classmethod
    def restore(cls, payload: dict[str, Any]) -> "TwoAgentRuntime":
        agents = payload["agents"]
        starts = payload.get("starts") or [[8, 16], [12, 16]]
        rt = cls(
            seed=int(payload.get("seed", 17)),
            starts=(tuple(starts[0]), tuple(starts[1])),
            contact_enabled=bool(payload.get("contact_enabled", True)),
            field_coupling_enabled=bool(payload.get("field_coupling_enabled", True)),
            signal_enabled=bool(payload.get("signal_enabled", False)),
            process_order=tuple(payload.get("process_order") or (0, 1)),
            independent_agent_seeds=bool(payload.get("independent_agent_seeds", True)),
        )
        restored: list[PhysicalSystemRuntime] = []
        for i, ag in enumerate(agents):
            if i == 0:
                restored.append(PhysicalSystemRuntime.restore(ag, world_seed=rt.seed, shared_world_member=True))
            else:
                payload_i = deepcopy(ag)
                payload_i["world"] = agents[0]["world"]
                ri = PhysicalSystemRuntime.restore(payload_i, world_seed=rt.seed, shared_world_member=True)
                ri.world = restored[0].world
                restored.append(ri)
        rt.slots = restored
        rt.world = restored[0].world
        rt.config = restored[0].config
        for i, slot in enumerate(rt.slots):
            slot.technical_id = f"agent_{i}"
            slot._defer_manipulator_world = True
            slot._lps_parent_managed = True
            slot.world = rt.world
        from mechanistic_mind.physical_system.physical_manipulator import sanitize_attachments
        sanitize_attachments(rt.world, {str(s.technical_id) for s in rt.slots})
        ident = payload.get("model") if isinstance(payload.get("model"), dict) else {}
        preset = ident.get("public_preset") or ident.get("model_line")
        if preset:
            from mechanistic_mind.model.lines import stamp_config_from_preset

            stamp_config_from_preset(rt.config, ident.get("public_preset") or ident.get("model_line"))
            for slot in rt.slots:
                stamp_config_from_preset(slot.config, ident.get("public_preset") or ident.get("model_line"))
        from mechanistic_mind.physical_system.procedural_surface_columns import (
            ensure_surface_columns_for_runtime,
        )
        ensure_surface_columns_for_runtime(rt.world, rt.config, experiment_seed=rt.seed)
        from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
            ensure_state as ensure_volumetric_occupancy_for_runtime,
        )
        ensure_volumetric_occupancy_for_runtime(rt.world, rt.config)
        from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
            ensure_state as ensure_occupancy_support_contact_for_runtime,
        )
        ensure_occupancy_support_contact_for_runtime(rt.world, rt.config)
        from mechanistic_mind.physical_system.volumetric_world_material_separation import (
            ensure_state as ensure_volumetric_separation_for_runtime,
        )
        ensure_volumetric_separation_for_runtime(rt.world, rt.config)
        from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
            ensure_state as ensure_volumetric_reintegration_for_runtime,
        )
        ensure_volumetric_reintegration_for_runtime(rt.world, rt.config)
        from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
            ensure_state as ensure_vw5_bridge_for_runtime,
        )
        ensure_vw5_bridge_for_runtime(rt.world, rt.config)
        from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
            ensure_state as ensure_vw6_vision_for_runtime,
        )
        ensure_vw6_vision_for_runtime(rt.world, rt.config)
        setattr(rt.world, "_physical_system_config", rt.config)
        rt._pending_sources = []
        rt.last_signal_receipt = None
        rt.last_contact = None
        rt.last_contacts = []
        rt.experimenter_slot = payload.get("experimenter_slot")
        if rt.experimenter_slot is not None:
            rt.experimenter_slot = int(rt.experimenter_slot)
            if 0 <= rt.experimenter_slot < len(rt.slots):
                rt.slots[rt.experimenter_slot]._experimenter_controlled = True  # type: ignore[attr-defined]
        # Align stats / process order with slot count
        while len(rt._agent_stats) < len(rt.slots):
            rt._agent_stats.append(_empty_agent_stats())
            rt._prev_xy.append(None)
        rt.process_order = tuple(range(len(rt.slots)))
        # Shared-world finalization, exactly once, after every slot, body pose, ResourceObject, holder
        # attachment (sanitized above with all slot ids) and the experimenter slot are bound: rebuild
        # the derived multi-content spatial index from authoritative state. No tick, no physics, no
        # receipts; slot restores ran with shared_world_member=True and did not build it.
        from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime, rebuild_after_restore

        rebuild_after_restore(rt.world, body_refs_for_runtime(rt), tick=int(rt.tick), config=rt.config)
        rt._lps_bind()
        return rt
