"""Zero-organism planet runtime with bounded telemetry."""
from __future__ import annotations

from typing import Any

import numpy as np

from mechanistic_mind.planet.boundary import boundary_to_dict, mask_sha256
from mechanistic_mind.planet.config import PlanetConfig, default_planet_config
from mechanistic_mind.planet.dynamics import step_planet
from mechanistic_mind.planet.forcing import forcing_field, forcing_phase_fast
from mechanistic_mind.planet.state import PlanetState, initialize_planet


def snapshot_stats(state: PlanetState, cfg: PlanetConfig, seed: int) -> dict[str, Any]:
    F = forcing_field(cfg, max(0, state.tick - 1), *state.T.shape, seed=seed)
    return {
        "tick": state.tick,
        "T_mean": float(state.T.mean()),
        "T_std": float(state.T.std()),
        "T_min": float(state.T.min()),
        "T_max": float(state.T.max()),
        "F_mean": float(F.mean()),
        "F_max": float(F.max()),
        "speed_mean": float(np.hypot(state.vx, state.vy).mean()),
        "speed_max": float(np.hypot(state.vx, state.vy).max()),
        "M0_sum": float(state.M[0].sum()),
        "M1_sum": float(state.M[1].sum()) if state.M.shape[0] > 1 else 0.0,
        "M2_sum": float(state.M[2].sum()) if state.M.shape[0] > 2 else 0.0,
        "M_total": float(state.M.sum()),
        "u_abs_mean": float(np.abs(state.u).mean()),
        "u_abs_max": float(np.abs(state.u).max()),
        "matter_err": float(state.M.sum() - state.matter_initial),
        "energy_in_cum": state.energy_in_cum,
        "energy_diss_cum": state.energy_diss_cum,
        "clip_counts": dict(state.clip_counts),
        "forcing_phase_fast_observer": forcing_phase_fast(state.tick, cfg.F_fast_period),
        "external_material_boundary": boundary_to_dict(state.external_material_boundary),
        "external_material_boundary_mask_sha256": mask_sha256(
            state.external_material_boundary.contact_mask
        ),
    }


def run_planet(
    *,
    seed: int = 17,
    horizon: int = 800,
    config: PlanetConfig | None = None,
    snapshot_every: int = 20,
    impulse_at: int | None = None,
    impulse_amp: float = 1.0,
    impulse_y: int | None = None,
    impulse_x: int | None = None,
) -> dict[str, Any]:
    cfg = config or default_planet_config()
    state = initialize_planet(cfg, seed=seed)
    series: list[dict[str, Any]] = []
    # store sparse field probes: center and seam-adjacent columns
    probes_T = []
    h, w = state.T.shape
    cy, cx = h // 2, w // 2
    series.append(snapshot_stats(state, cfg, seed))
    for t in range(horizon):
        impulse = None
        if impulse_at is not None and t == impulse_at:
            impulse = np.zeros_like(state.u)
            iy = h // 2 if impulse_y is None else int(impulse_y) % h
            ix = w // 2 if impulse_x is None else int(impulse_x) % w
            impulse[iy, ix] = float(impulse_amp)
        step_planet(state, cfg, seed=seed, impulse=impulse)
        if (t + 1) % snapshot_every == 0 or t + 1 == horizon:
            series.append(snapshot_stats(state, cfg, seed))
            probes_T.append({"tick": state.tick, "center": float(state.T[cy, cx]), "seam": float(state.T[cy, 0])})
    return {
        "seed": seed,
        "horizon": horizon,
        "config": cfg.to_dict(),
        "series": series,
        "probes_T": probes_T,
        "final": {
            "T": state.T,
            "M": state.M,
            "vx": state.vx,
            "vy": state.vy,
            "u": state.u,
            "capacity": state.capacity,
            "conductivity": state.conductivity,
            "tick": state.tick,
            "matter_initial": state.matter_initial,
            "clip_counts": dict(state.clip_counts),
        },
        "state": state,
    }




def serialize_planet_state(state: PlanetState, cfg: PlanetConfig) -> dict[str, Any]:
    """Exact snapshot including resolved external material boundary (OPEN-5)."""
    out = {
        "tick": int(state.tick),
        "T": state.T.tolist(),
        "M": state.M.tolist(),
        "vx": state.vx.tolist(),
        "vy": state.vy.tolist(),
        "u": state.u.tolist(),
        "u_prev": state.u_prev.tolist(),
        "capacity": state.capacity.tolist(),
        "conductivity": state.conductivity.tolist(),
        "matter_initial": float(state.matter_initial),
        "energy_in_cum": float(state.energy_in_cum),
        "energy_diss_cum": float(state.energy_diss_cum),
        "clip_counts": dict(state.clip_counts),
        "config": cfg.to_dict(),
        "external_material_boundary": boundary_to_dict(state.external_material_boundary),
        "external_material_boundary_mask_sha256": mask_sha256(
            state.external_material_boundary.contact_mask
        ),
        "R": None if getattr(state, "R", None) is None else np.asarray(state.R).tolist(),
        "R_A": None if getattr(state, "R_A", None) is None else np.asarray(state.R_A).tolist(),
        "R_B": None if getattr(state, "R_B", None) is None else np.asarray(state.R_B).tolist(),
        "FIELD_A": None if getattr(state, "FIELD_A", None) is None else np.asarray(state.FIELD_A).tolist(),
        "FIELD_B": None if getattr(state, "FIELD_B", None) is None else np.asarray(state.FIELD_B).tolist(),
        "terrain_potential": (
            None if getattr(state, "terrain_potential", None) is None
            else np.asarray(state.terrain_potential).tolist()
        ),
        "terrain_drag": (
            None if getattr(state, "terrain_drag", None) is None
            else np.asarray(state.terrain_drag).tolist()
        ),
        "terrain_grad_y": (
            None if getattr(state, "terrain_grad_y", None) is None
            else np.asarray(state.terrain_grad_y).tolist()
        ),
        "terrain_grad_x": (
            None if getattr(state, "terrain_grad_x", None) is None
            else np.asarray(state.terrain_grad_x).tolist()
        ),
        "terrain_meta": (
            None if getattr(state, "terrain_meta", None) is None
            else dict(state.terrain_meta)
        ),
        "resource_geo_suit_A": (
            None if getattr(state, "resource_geo_suit_A", None) is None
            else np.asarray(state.resource_geo_suit_A).tolist()
        ),
        "resource_geo_suit_B": (
            None if getattr(state, "resource_geo_suit_B", None) is None
            else np.asarray(state.resource_geo_suit_B).tolist()
        ),
        "ambient_fx": (
            None if getattr(state, "ambient_fx", None) is None
            else np.asarray(state.ambient_fx).tolist()
        ),
        "ambient_fy": (
            None if getattr(state, "ambient_fy", None) is None
            else np.asarray(state.ambient_fy).tolist()
        ),
        "ambient_meta": (
            None if getattr(state, "ambient_meta", None) is None
            else dict(state.ambient_meta)
        ),
        "surface_response": (
            None if getattr(state, "surface_response", None) is None
            else np.asarray(state.surface_response).tolist()
        ),
        "surface_meta": (
            None if getattr(state, "surface_meta", None) is None
            else dict(state.surface_meta)
        ),
        "illumination_intensity": getattr(state, "illumination_intensity", None),
        "illumination_meta": (
            None if getattr(state, "illumination_meta", None) is None
            else dict(state.illumination_meta)
        ),
        "surface_optical": (
            None if getattr(state, "surface_optical", None) is None
            else np.asarray(state.surface_optical).tolist()
        ),
        "surface_optical_meta": (
            None if getattr(state, "surface_optical_meta", None) is None
            else dict(state.surface_optical_meta)
        ),
        "OSC_BANDS": (
            None if getattr(state, "OSC_BANDS", None) is None
            else np.asarray(state.OSC_BANDS).tolist()
        ),
        "experiment_seed": (
            int((state.terrain_meta or {}).get("experiment_seed"))
            if getattr(state, "terrain_meta", None)
            and (state.terrain_meta or {}).get("experiment_seed") is not None
            else None
        ),
    }
    objs = getattr(state, "resource_objects", None) or []
    next_id = int(getattr(state, "resource_object_next_id", 1) or 1)
    if objs or next_id > 1:
        from mechanistic_mind.physical_system.resource_objects import serialize_resource_objects
        out["resource_objects"] = serialize_resource_objects(state)
    from mechanistic_mind.physical_system.explicit_surface_deposition import serialize_surface_deposits

    deposits = serialize_surface_deposits(state)
    if deposits:
        out["surface_material_deposits"] = deposits
    generation = int(getattr(state, "surface_optical_coating_generation", 0) or 0)
    if generation:
        out["surface_optical_coating_generation"] = generation
    sequence = int(getattr(state, "material_transaction_sequence", 0) or 0)
    if sequence:
        out["material_transaction_sequence"] = sequence
    committed_ids = list(getattr(state, "material_transaction_committed_ids", None) or [])
    if committed_ids:
        out["material_transaction_committed_ids"] = committed_ids[-64:]
    transaction_history = list(getattr(state, "material_transaction_history", None) or [])
    if transaction_history:
        out["material_transaction_history"] = transaction_history[-16:]
    generation = int(getattr(state, "spatial_index_generation", 0) or 0)
    if generation:
        out["spatial_index_generation"] = generation
        out["spatial_index_schema"] = str(getattr(state, "spatial_index_schema", "") or "MULTI_CONTENT_SPATIAL_INDEX_V1")
        checksum = getattr(state, "spatial_index_checksum", None)
        if checksum:
            out["spatial_index_checksum"] = str(checksum)
    if getattr(state, "surface_columns", None) is not None:
        from mechanistic_mind.physical_system.procedural_surface_columns import serialize_surface_columns

        columns = serialize_surface_columns(state)
        if columns:
            out["surface_columns"] = columns
    if getattr(state, "volumetric_occupancy", None) is not None:
        from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
            serialize_volumetric_occupancy,
        )

        vo = serialize_volumetric_occupancy(state)
        if vo:
            out["volumetric_occupancy"] = vo
    if getattr(state, "local_signal_transport", None) is not None:
        from mechanistic_mind.physical_system.local_physical_signal_transport import serialize_state

        out["local_signal_transport"] = serialize_state(state.local_signal_transport)
    if getattr(state, "contact_acoustic_state", None) is not None:
        from mechanistic_mind.physical_system.physical_contact_acoustic_emission import (
            serialize_state as pca_serialize,
        )

        out["contact_acoustic_state"] = pca_serialize(state.contact_acoustic_state)
    if getattr(state, "free_object_kinematics_state", None) is not None:
        from mechanistic_mind.physical_system.free_resource_object_kinematics import (
            serialize_state as fok_serialize,
        )

        out["free_object_kinematics_state"] = fok_serialize(state.free_object_kinematics_state)
    if getattr(state, "body_object_contact_state", None) is not None:
        from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
            serialize_state as boc_serialize,
        )

        out["body_object_contact_state"] = boc_serialize(state.body_object_contact_state)
    if getattr(state, "body_object_contact_impulse_state", None) is not None:
        from mechanistic_mind.physical_system.body_resource_object_contact_impulse import (
            serialize_state as boi_serialize,
        )

        out["body_object_contact_impulse_state"] = boi_serialize(state.body_object_contact_impulse_state)
    if getattr(state, "body_object_impact_acoustic_state", None) is not None:
        from mechanistic_mind.physical_system.body_resource_object_impact_acoustic_emission import (
            serialize_state as oia_serialize,
        )

        out["body_object_impact_acoustic_state"] = oia_serialize(state.body_object_impact_acoustic_state)
    if getattr(state, "resource_object_pair_contact_state", None) is not None:
        from mechanistic_mind.physical_system.physical_resource_object_pair_contact import (
            serialize_state as ooc_serialize,
        )

        out["resource_object_pair_contact_state"] = ooc_serialize(state.resource_object_pair_contact_state)
    if getattr(state, "resource_object_pair_contact_impulse_state", None) is not None:
        from mechanistic_mind.physical_system.resource_object_pair_contact_impulse import (
            serialize_state as ooi_serialize,
        )

        out["resource_object_pair_contact_impulse_state"] = ooi_serialize(
            state.resource_object_pair_contact_impulse_state
        )
    if getattr(state, "resource_object_pair_impact_acoustic_state", None) is not None:
        from mechanistic_mind.physical_system.resource_object_pair_impact_acoustic_emission import (
            serialize_state as ooia_serialize,
        )

        out["resource_object_pair_impact_acoustic_state"] = ooia_serialize(
            state.resource_object_pair_impact_acoustic_state
        )
    if getattr(state, "authoritative_physical_acoustic_stream_state", None) is not None:
        from mechanistic_mind.physical_system.authoritative_physical_acoustic_stream_contract import (
            serialize_state as apas_serialize,
        )

        out["authoritative_physical_acoustic_stream_state"] = apas_serialize(
            state.authoritative_physical_acoustic_stream_state
        )
    if getattr(state, "observer_acoustic_probe_state", None) is not None:
        from mechanistic_mind.physical_system.observer_acoustic_probe import (
            serialize_state as oap_serialize,
        )

        out["observer_acoustic_probe_state"] = oap_serialize(state.observer_acoustic_probe_state)
    if getattr(state, "selected_organism_auditory_boundary_state", None) is not None:
        from mechanistic_mind.physical_system.selected_organism_auditory_boundary_receipt import (
            serialize_state as soab_serialize,
        )

        out["selected_organism_auditory_boundary_state"] = soab_serialize(
            state.selected_organism_auditory_boundary_state
        )
    if getattr(state, "selected_organism_volumetric_vision_state", None) is not None:
        from mechanistic_mind.physical_system.selected_organism_volumetric_vision_view import (
            serialize_state as sovv_serialize,
        )

        out["selected_organism_volumetric_vision_state"] = sovv_serialize(
            state.selected_organism_volumetric_vision_state
        )
    if getattr(state, "organism_receptor_grounded_3d_fpv_state", None) is not None:
        from mechanistic_mind.physical_system.organism_receptor_grounded_3d_fpv import (
            serialize_state as fpv_serialize,
        )

        out["organism_receptor_grounded_3d_fpv_state"] = fpv_serialize(
            state.organism_receptor_grounded_3d_fpv_state
        )
    if getattr(state, "organism_auditory_transformation_trace_state", None) is not None:
        from mechanistic_mind.physical_system.organism_auditory_transformation_trace import (
            serialize_state as oatt_serialize,
        )

        out["organism_auditory_transformation_trace_state"] = oatt_serialize(
            state.organism_auditory_transformation_trace_state
        )
    if getattr(state, "held_foreign_body_contact_state", None) is not None:
        from mechanistic_mind.physical_system.held_resource_object_foreign_body_contact import (
            serialize_state as hfc_serialize,
        )

        out["held_foreign_body_contact_state"] = hfc_serialize(state.held_foreign_body_contact_state)
    return out


def restore_planet_state(payload: dict[str, Any]) -> tuple[PlanetState, PlanetConfig]:
    """Restore planet + boundary. Missing boundary fields => OFF."""
    from mechanistic_mind.planet.boundary import boundary_from_dict

    cfg = PlanetConfig.from_dict(payload.get("config", {}))
    n = int(np.asarray(payload["M"]).shape[0])
    b = boundary_from_dict(payload.get("external_material_boundary"), n_materials=n)
    st = PlanetState(
        tick=int(payload["tick"]),
        T=np.asarray(payload["T"], dtype=np.float64),
        M=np.asarray(payload["M"], dtype=np.float64),
        vx=np.asarray(payload["vx"], dtype=np.float64),
        vy=np.asarray(payload["vy"], dtype=np.float64),
        u=np.asarray(payload["u"], dtype=np.float64),
        u_prev=np.asarray(payload["u_prev"], dtype=np.float64),
        capacity=np.asarray(payload["capacity"], dtype=np.float64),
        conductivity=np.asarray(payload["conductivity"], dtype=np.float64),
        matter_initial=float(payload["matter_initial"]),
        energy_in_cum=float(payload.get("energy_in_cum", 0.0)),
        energy_diss_cum=float(payload.get("energy_diss_cum", 0.0)),
        clip_counts=dict(payload.get("clip_counts", {"T": 0, "M": 0, "v": 0, "u": 0})),
        external_material_boundary=b,
        R=(
            None if payload.get("R") is None
            else np.asarray(payload["R"], dtype=np.float64)
        ),
        R_A=(
            None if payload.get("R_A") is None
            else np.asarray(payload["R_A"], dtype=np.float64)
        ),
        R_B=(
            None if payload.get("R_B") is None
            else np.asarray(payload["R_B"], dtype=np.float64)
        ),
        FIELD_A=(
            None if payload.get("FIELD_A") is None
            else np.asarray(payload["FIELD_A"], dtype=np.float64)
        ),
        FIELD_B=(
            None if payload.get("FIELD_B") is None
            else np.asarray(payload["FIELD_B"], dtype=np.float64)
        ),
        terrain_potential=(
            None if payload.get("terrain_potential") is None
            else np.asarray(payload["terrain_potential"], dtype=np.float64)
        ),
        terrain_drag=(
            None if payload.get("terrain_drag") is None
            else np.asarray(payload["terrain_drag"], dtype=np.float64)
        ),
        terrain_grad_y=(
            None if payload.get("terrain_grad_y") is None
            else np.asarray(payload["terrain_grad_y"], dtype=np.float64)
        ),
        terrain_grad_x=(
            None if payload.get("terrain_grad_x") is None
            else np.asarray(payload["terrain_grad_x"], dtype=np.float64)
        ),
        terrain_meta=(
            None if payload.get("terrain_meta") is None
            else dict(payload["terrain_meta"])
        ),
        resource_geo_suit_A=(
            None if payload.get("resource_geo_suit_A") is None
            else np.asarray(payload["resource_geo_suit_A"], dtype=np.float64)
        ),
        resource_geo_suit_B=(
            None if payload.get("resource_geo_suit_B") is None
            else np.asarray(payload["resource_geo_suit_B"], dtype=np.float64)
        ),
        ambient_fx=(
            None if payload.get("ambient_fx") is None
            else np.asarray(payload["ambient_fx"], dtype=np.float64)
        ),
        ambient_fy=(
            None if payload.get("ambient_fy") is None
            else np.asarray(payload["ambient_fy"], dtype=np.float64)
        ),
        ambient_meta=(
            None if payload.get("ambient_meta") is None
            else dict(payload["ambient_meta"])
        ),
        surface_response=(
            None if payload.get("surface_response") is None
            else np.asarray(payload["surface_response"], dtype=np.float64)
        ),
        surface_meta=(
            None if payload.get("surface_meta") is None
            else dict(payload["surface_meta"])
        ),
        illumination_intensity=(
            None if payload.get("illumination_intensity") is None
            else float(payload["illumination_intensity"])
        ),
        illumination_meta=(
            None if payload.get("illumination_meta") is None
            else dict(payload["illumination_meta"])
        ),
        surface_optical=(
            None if payload.get("surface_optical") is None
            else np.asarray(payload["surface_optical"], dtype=np.float64)
        ),
        surface_optical_meta=(
            None if payload.get("surface_optical_meta") is None
            else dict(payload["surface_optical_meta"])
        ),
        OSC_BANDS=(
            None if payload.get("OSC_BANDS") is None
            else np.asarray(payload["OSC_BANDS"], dtype=np.float64)
        ),
    )
    from mechanistic_mind.physical_system.resource_objects import restore_resource_objects

    restore_resource_objects(st, payload.get("resource_objects"))
    from mechanistic_mind.physical_system.explicit_surface_deposition import restore_surface_deposits

    restore_surface_deposits(st, payload.get("surface_material_deposits"))
    st.surface_optical_coating_generation = int(payload.get("surface_optical_coating_generation") or 0)
    st.material_transaction_sequence = int(payload.get("material_transaction_sequence") or 0)
    st.material_transaction_committed_ids = list(payload.get("material_transaction_committed_ids") or [])
    st.material_transaction_history = list(payload.get("material_transaction_history") or [])
    st.spatial_index_generation = int(payload.get("spatial_index_generation") or 0)
    st.spatial_index_schema = str(payload.get("spatial_index_schema") or "")
    st.spatial_index_checksum = str(payload.get("spatial_index_checksum") or "")
    if payload.get("surface_columns"):
        from mechanistic_mind.physical_system.procedural_surface_columns import restore_surface_columns

        restore_surface_columns(st, payload.get("surface_columns"), tick=int(getattr(st, "tick", 0) or 0))
    if payload.get("volumetric_occupancy"):
        from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
            restore_volumetric_occupancy,
        )

        restore_volumetric_occupancy(
            st, payload.get("volumetric_occupancy"), tick=int(getattr(st, "tick", 0) or 0)
        )
    if payload.get("local_signal_transport"):
        # Raw payload; the physical runtime restores it against its own config (missing -> OFF).
        st._local_signal_transport_payload = dict(payload.get("local_signal_transport"))
    if payload.get("contact_acoustic_state"):
        # Raw payload; restored against the runtime config (missing field -> mechanism OFF).
        st._contact_acoustic_payload = dict(payload.get("contact_acoustic_state"))
    if payload.get("free_object_kinematics_state"):
        # Raw payload; restored against the runtime config (missing field -> mechanism OFF).
        st._free_object_kinematics_payload = dict(payload.get("free_object_kinematics_state"))
    if payload.get("body_object_contact_state"):
        # Raw payload; restored against the runtime config (missing field -> mechanism OFF).
        st._body_object_contact_payload = dict(payload.get("body_object_contact_state"))
    if payload.get("body_object_contact_impulse_state"):
        st._body_object_contact_impulse_payload = dict(payload.get("body_object_contact_impulse_state"))
    if payload.get("body_object_impact_acoustic_state"):
        st._body_object_impact_acoustic_payload = dict(payload.get("body_object_impact_acoustic_state"))
    if payload.get("resource_object_pair_contact_state"):
        st._resource_object_pair_contact_payload = dict(payload.get("resource_object_pair_contact_state"))
    if payload.get("resource_object_pair_contact_impulse_state"):
        st._resource_object_pair_contact_impulse_payload = dict(
            payload.get("resource_object_pair_contact_impulse_state")
        )
    if payload.get("resource_object_pair_impact_acoustic_state"):
        st._resource_object_pair_impact_acoustic_payload = dict(
            payload.get("resource_object_pair_impact_acoustic_state")
        )
    if payload.get("authoritative_physical_acoustic_stream_state"):
        st._authoritative_physical_acoustic_stream_payload = dict(
            payload.get("authoritative_physical_acoustic_stream_state")
        )
    if payload.get("observer_acoustic_probe_state"):
        st._observer_acoustic_probe_payload = dict(payload.get("observer_acoustic_probe_state"))
    if payload.get("selected_organism_auditory_boundary_state"):
        st._selected_organism_auditory_boundary_payload = dict(
            payload.get("selected_organism_auditory_boundary_state")
        )
    if payload.get("selected_organism_volumetric_vision_state"):
        st._selected_organism_volumetric_vision_payload = dict(
            payload.get("selected_organism_volumetric_vision_state")
        )
    if payload.get("organism_receptor_grounded_3d_fpv_state"):
        st._organism_receptor_grounded_3d_fpv_payload = dict(
            payload.get("organism_receptor_grounded_3d_fpv_state")
        )
    if payload.get("organism_auditory_transformation_trace_state"):
        st._organism_auditory_transformation_trace_payload = dict(
            payload.get("organism_auditory_transformation_trace_state")
        )
    if payload.get("held_foreign_body_contact_state"):
        st._held_foreign_body_contact_payload = dict(payload.get("held_foreign_body_contact_state"))
    # Legacy snapshots without serialized grids but with terrain config enabled:
    # regenerate deterministically from experiment_seed + namespaced terrain_seed.
    te = getattr(cfg, "terrain", None)
    if (
        te is not None
        and bool(getattr(te, "enabled", False))
        and st.terrain_potential is None
    ):
        from mechanistic_mind.planet.terrain import install_terrain_on_planet

        seed = int(
            (payload.get("terrain_meta") or {}).get("experiment_seed")
            or payload.get("experiment_seed")
            or payload.get("seed")
            or 17
        )
        install_terrain_on_planet(st, experiment_seed=seed, config=te)
    elif st.terrain_meta is None and st.terrain_potential is not None:
        from mechanistic_mind.planet.terrain import build_terrain_metadata

        te2 = te or getattr(cfg, "terrain", None)
        if te2 is not None:
            st.terrain_meta = build_terrain_metadata(
                experiment_seed=int(payload.get("experiment_seed") or payload.get("seed") or 17),
                config=te2,
                potential=st.terrain_potential,
                drag=st.terrain_drag,
                height=int(st.T.shape[0]),
                width=int(st.T.shape[1]),
            )
            st.terrain_meta["enabled"] = True
    # Legacy snapshots without ambient grids but with ambient config enabled.
    ae = getattr(cfg, "ambient", None)
    if (
        ae is not None
        and bool(getattr(ae, "enabled", False))
        and st.ambient_fx is None
    ):
        from mechanistic_mind.planet.ambient import install_ambient_on_planet

        seed = int(
            (payload.get("ambient_meta") or {}).get("experiment_seed")
            or payload.get("experiment_seed")
            or payload.get("seed")
            or 17
        )
        install_ambient_on_planet(st, experiment_seed=seed, config=ae)
    return st, cfg
