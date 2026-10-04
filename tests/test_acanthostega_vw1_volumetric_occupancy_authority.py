"""VW1_VOLUMETRIC_OCCUPANCY_AUTHORITY_V1 — targeted state/query/Observer tests.

Prefer TOTAL_SIMULATED_TICKS = 0. No VW2 support/contact migration.
"""
from __future__ import annotations

import copy
import json
import math

import pytest

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def test_A_legacy_column_conversion_deterministic():
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        INTERVAL_ENDPOINT_SEMANTICS,
        intervals_from_legacy_column,
    )

    H = 10.0
    layers = [
        {
            "top_depth": 0.0,
            "bottom_depth": 1.5,
            "density": 1.2,
            "composition": [{"component_id": "soil", "quantity_per_area": 1.5}],
        },
        {
            "top_depth": 1.5,
            "bottom_depth": 3.0,
            "density": 2.0,
            "composition": [{"component_id": "rock", "quantity_per_area": 1.5}],
        },
    ]
    a = intervals_from_legacy_column(H, layers)
    b = intervals_from_legacy_column(H, layers)
    assert [(it.z_min, it.z_max, it.density, it.composition) for it in a] == [
        (it.z_min, it.z_max, it.density, it.composition) for it in b
    ]
    # depth [0, 1.5) -> z (8.5, 10.0]; depth [1.5, 3.0) -> z (7.0, 8.5]
    assert abs(a[0].z_min - 7.0) < 1e-12 and abs(a[0].z_max - 8.5) < 1e-12
    assert abs(a[1].z_min - 8.5) < 1e-12 and abs(a[1].z_max - 10.0) < 1e-12
    assert a[0].composition[0][0] == "rock"
    assert a[1].composition[0][0] == "soil"
    assert INTERVAL_ENDPOINT_SEMANTICS == "HALF_OPEN_LOWER_EXCLUSIVE_UPPER_INCLUSIVE"


def test_B_C_E_basic_occupancy_internal_gap_boundaries():
    from types import SimpleNamespace

    import numpy as np

    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        VolumetricWorldMaterialOccupancyConfig,
        column_view,
        ensure_state,
        material_at,
        occupancy_at,
        set_volumetric_column,
    )

    w = SimpleNamespace(T=np.zeros((16, 16)))
    cfg = SimpleNamespace(
        model_line="ACANTHOSTEGA",
        volumetric_world_material_occupancy=VolumetricWorldMaterialOccupancyConfig(enabled=True),
    )
    ensure_state(w, cfg)
    lo = OccupiedZInterval(1.0, 3.0, 1.0, (("soil", 2.0),))
    hi = OccupiedZInterval(5.0, 7.0, 1.5, (("rock", 2.0),))
    set_volumetric_column(w, 4, 5, [lo, hi])

    assert occupancy_at(w, 4, 5, 2.0) is True
    assert occupancy_at(w, 4, 5, 4.0) is False
    assert occupancy_at(w, 4, 5, 6.0) is True
    # endpoints: occupied iff z_min < z ≤ z_max
    assert occupancy_at(w, 4, 5, 1.0) is False
    assert occupancy_at(w, 4, 5, 3.0) is True
    assert occupancy_at(w, 4, 5, 5.0) is False
    assert occupancy_at(w, 4, 5, 7.0) is True

    view = column_view(w, 4, 5)
    assert view["source"] == "SPARSE_AUTHORITY"
    assert len(view["occupied_intervals"]) == 2
    assert len(view["free_gaps"]) == 1
    gap = view["free_gaps"][0]
    assert abs(float(gap["z_lo"]) - 3.0) < 1e-12
    assert abs(float(gap["z_hi"]) - 5.0) < 1e-12
    mat = material_at(w, 4, 5, 2.0)
    assert mat["occupied"] is True and mat["interval"]["composition"][0]["component_id"] == "soil"
    assert material_at(w, 4, 5, 4.0)["occupied"] is False


def test_D_multiple_material_regions_preserved():
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import OccupiedZInterval, canonicalize_intervals

    a = OccupiedZInterval(0.0, 1.0, 1.0, (("soil", 1.0),))
    b = OccupiedZInterval(1.0, 2.0, 1.0, (("rock", 1.0),))
    out = canonicalize_intervals([a, b], merge_compatible_abutting=True)
    assert len(out) == 2  # incompatible compositions stay distinct
    c = OccupiedZInterval(2.0, 3.0, 1.0, (("rock", 1.0),))
    merged = canonicalize_intervals([b, c], merge_compatible_abutting=True)
    assert len(merged) == 1 and abs(merged[0].z_max - 3.0) < 1e-12


def test_F_H_canonicalization_determinism():
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        canonicalize_intervals,
    )

    a = OccupiedZInterval(2.0, 3.0, 1.0, (("a", 1.0),))
    b = OccupiedZInterval(0.0, 1.0, 1.0, (("b", 1.0),))
    c1 = canonicalize_intervals([a, b])
    c2 = canonicalize_intervals([b, a])
    assert [(it.z_min, it.z_max) for it in c1] == [(it.z_min, it.z_max) for it in c2]
    with pytest.raises(Exception):
        canonicalize_intervals(
            [OccupiedZInterval(0.0, 2.0, 1.0, (("x", 1.0),)), OccupiedZInterval(1.0, 3.0, 1.0, (("y", 1.0),))]
        )
    with pytest.raises(Exception):
        OccupiedZInterval(1.0, 1.0, 1.0, (("x", 1.0),))


def test_G_snapshot_restore_non_heightfield():
    from types import SimpleNamespace

    import numpy as np

    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        VolumetricWorldMaterialOccupancyConfig,
        ensure_state,
        occupancy_at,
        restore_volumetric_occupancy,
        serialize_volumetric_occupancy,
        set_volumetric_column,
        state_of,
    )

    w = SimpleNamespace(T=np.zeros((12, 12)))
    cfg = SimpleNamespace(
        model_line="ACANTHOSTEGA",
        volumetric_world_material_occupancy=VolumetricWorldMaterialOccupancyConfig(enabled=True),
    )
    ensure_state(w, cfg)
    set_volumetric_column(
        w,
        2,
        3,
        [
            OccupiedZInterval(0.5, 2.0, 1.1, (("soil", 1.5),)),
            OccupiedZInterval(4.0, 5.5, 2.2, (("rock", 1.5),)),
        ],
    )
    snap = serialize_volumetric_occupancy(w)
    dig = state_of(w).digest()
    w2 = SimpleNamespace(T=np.zeros((12, 12)))
    restore_volumetric_occupancy(w2, snap)
    assert state_of(w2).digest() == dig
    assert occupancy_at(w2, 2, 3, 1.0) and not occupancy_at(w2, 2, 3, 3.0) and occupancy_at(w2, 2, 3, 5.0)
    # JSON round-trip stability (sorted keys)
    s1 = json.dumps(snap, sort_keys=True, separators=(",", ":"))
    s2 = json.dumps(json.loads(s1), sort_keys=True, separators=(",", ":"))
    assert s1 == s2


def test_I_J_xy_wrap_z_no_wrap():
    from types import SimpleNamespace

    import numpy as np

    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        VolumetricWorldMaterialOccupancyConfig,
        ensure_state,
        occupancy_at,
        set_volumetric_column,
        wrap_cell,
        state_of,
    )

    w = SimpleNamespace(T=np.zeros((8, 8)))  # height=8, width=8
    cfg = SimpleNamespace(
        model_line="ACANTHOSTEGA",
        volumetric_world_material_occupancy=VolumetricWorldMaterialOccupancyConfig(enabled=True),
    )
    st = ensure_state(w, cfg)
    set_volumetric_column(w, 0, 0, [OccupiedZInterval(1.0, 2.0, 1.0, (("soil", 1.0),))])
    assert wrap_cell(st, 8, 0) == (0, 0)
    assert occupancy_at(w, 8, 0, 1.5) is True
    # Z is absolute — no modular wrap into occupied band from far below/above
    assert occupancy_at(w, 0, 0, 1.5 + 1000.0) is False
    assert occupancy_at(w, 0, 0, 1.5 - 1000.0) is False
    assert state_of(w).width == 8 and state_of(w).height == 8


def test_K_legacy_physics_preservation_surface_unchanged():
    """VW1 alone does not change PSC surface elevation used by pre-VW2 consumers."""
    from mechanistic_mind.model.acanthostega import acanthostega_volumetric_occupancy_config
    from mechanistic_mind.physical_system.procedural_surface_columns import resolved_column_at
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        compatibility_surface_elevation,
        occupied_intervals_at,
        state_of,
    )

    cfg = acanthostega_volumetric_occupancy_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    assert state_of(rt.world) is not None
    col = resolved_column_at(rt.world, 3, 4, record=False)
    H = float(col["surface_elevation"])
    derived = compatibility_surface_elevation(rt.world, 3, 4)
    assert derived is not None and abs(float(derived) - H) < 1e-9
    intervals = occupied_intervals_at(rt.world, 3, 4)
    assert intervals and abs(float(intervals[-1].z_max) - H) < 1e-9
    # 0 ticks — no locomotion/support change exercised; surface identity preserved
    assert TICKS["n"] == 0


def test_L_M_observer_data_and_passivity():
    from mechanistic_mind.model.acanthostega import acanthostega_volumetric_occupancy_config
    from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        observer_column_inspector_payload,
        researcher_payload,
        set_volumetric_column,
        state_of,
    )
    from mechanistic_mind.ui.psy_observer_web.serialize import world_frame

    cfg = acanthostega_volumetric_occupancy_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=19, config=cfg)
    set_volumetric_column(
        rt.world,
        1,
        2,
        [
            OccupiedZInterval(0.0, 2.0, 1.0, (("soil", 2.0),)),
            OccupiedZInterval(4.0, 6.0, 1.2, (("rock", 2.0),)),
        ],
    )
    dig_before = state_of(rt.world).digest()
    hist_before = copy.deepcopy(state_of(rt.world).history)
    insp = observer_column_inspector_payload(rt.world, 1, 2)
    assert insp is not None
    assert insp["source"] == "SPARSE_AUTHORITY"
    assert len(insp["occupied_intervals"]) == 2
    assert len(insp["free_gaps"]) == 1
    assert insp["researcher_only_view"] is True
    assert state_of(rt.world).digest() == dig_before
    # history may grow only via explicit set; inspector must not mutate digest/history length beyond queries
    assert state_of(rt.world).history == hist_before

    payload = researcher_payload(rt.world)
    assert "volumetric_occupancy" in payload
    assert payload["volumetric_occupancy"]["authority"] == "AUTHORITATIVE_WORLD_MATERIAL_OCCUPANCY_ABSOLUTE_Z"
    assert state_of(rt.world).digest() == dig_before

    frame = world_frame(rt)
    assert frame.get("volumetric_occupancy")
    assert frame["volumetric_occupancy"]["schema"] == "VW1_VOLUMETRIC_OCCUPANCY_AUTHORITY_V1"

    for tok in (
        "VW1_VOLUMETRIC_OCCUPANCY_AUTHORITY_V1",
        "volumetric_occupancy",
        "occupied_intervals",
        "free_gaps",
        "AUTHORITATIVE_WORLD_MATERIAL_OCCUPANCY_ABSOLUTE_Z",
    ):
        assert tok in FORBIDDEN_TOKENS
    audit_cognition_payload({"note": "clean"})


def test_ordinary_world_snapshot_includes_empty_sparse_map():
    from mechanistic_mind.model.acanthostega import acanthostega_volumetric_occupancy_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    cfg = acanthostega_volumetric_occupancy_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=21, config=cfg)
    snap = rt.snapshot()
    vo = snap["world"]["volumetric_occupancy"]
    assert vo["columns"] == []
    assert vo["schema"] == "VOLUMETRIC_OCCUPANCY_SNAPSHOT_V1"
    # restore via runtime path preserves empty sparse authority
    rt2 = PhysicalSystemRuntime(seed=21, config=cfg)
    rt2.restore(snap)
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import state_of

    assert state_of(rt2.world) is not None
    assert len(state_of(rt2.world).columns) == 0


def test_tick_budget():
    assert TICKS["n"] == 0
