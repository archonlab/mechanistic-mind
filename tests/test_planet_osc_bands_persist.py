"""Planet snapshot must persist OSC_BANDS; restore must sync embodiment DOFs."""
from __future__ import annotations

import json
from copy import deepcopy
from io import StringIO

import numpy as np

from mechanistic_mind.planet.runtime import restore_planet_state, serialize_planet_state
from mechanistic_mind.physical_system.oscillatory_signaling import OscillatorySignalingConfig, ensure_osc_fields
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.run_finalize import dump_persist


def test_osc_bands_serialize_restore_exact():
    rt = TwoAgentRuntime(seed=21, signal_enabled=True)
    cfg = OscillatorySignalingConfig()
    bands = ensure_osc_fields(rt.world, cfg)
    bands += 0.123456789
    payload = serialize_planet_state(rt.world, rt.slots[0].config.planet)
    assert payload.get("OSC_BANDS") is not None
    world2, _ = restore_planet_state(payload)
    assert np.array_equal(np.asarray(rt.world.OSC_BANDS), np.asarray(world2.OSC_BANDS))


def test_json_roundtrip_osc_bands_close():
    rt = TwoAgentRuntime(seed=21, signal_enabled=True)
    cfg = OscillatorySignalingConfig()
    bands = ensure_osc_fields(rt.world, cfg)
    rng = np.random.default_rng(0)
    bands[:] = rng.random(bands.shape)
    snap = serialize_planet_state(rt.world, rt.slots[0].config.planet)
    buf = StringIO()
    dump_persist(snap, buf, compact=True)
    loaded = json.loads(buf.getvalue())
    world2, _ = restore_planet_state(loaded)
    assert np.array_equal(rt.world.OSC_BANDS, world2.OSC_BANDS)


def test_restore_syncs_head_flag_and_matches_exo():
    from experiments.run_beta31_pe_forgotten_compaction import make_runtime

    rt = make_runtime()
    for _ in range(10):
        rt.step(n=1)
    rest = TwoAgentRuntime.restore(deepcopy(rt.snapshot(persist=False)))
    assert bool(getattr(rt.slots[0].body, "_articulated_head_enabled", False)) is True
    assert bool(getattr(rest.slots[0].body, "_articulated_head_enabled", False)) is True
    assert rt.observations() == rest.observations()
