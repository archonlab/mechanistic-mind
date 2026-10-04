"""Regression: Beta 4 public presets must never stamp/identity as Tiktaalik."""
from __future__ import annotations

from mechanistic_mind.model.lines import (
    identity_for_config,
    identity_from_public_preset,
    stamp_config_from_preset,
)
from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
    bnlt_move_breakaway_locomotion_repair_is_active,
)
from mechanistic_mind.physical_system.experiment_canonical import (
    ACANTHOSTEGA_PUBLIC_PRESET_IDS,
    PRESET_ACANTHOSTEGA_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR,
    PRESET_ACANTHOSTEGA_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION,
    is_acanthostega_public_preset,
    merge_canonical,
    preset_canonical,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession


BETA4_TIP = PRESET_ACANTHOSTEGA_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR
BETA4_RCSS = PRESET_ACANTHOSTEGA_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION


def test_beta4_ids_registered_as_acanthostega():
    assert BETA4_TIP in ACANTHOSTEGA_PUBLIC_PRESET_IDS
    assert BETA4_RCSS in ACANTHOSTEGA_PUBLIC_PRESET_IDS
    assert is_acanthostega_public_preset(BETA4_TIP)
    assert is_acanthostega_public_preset(BETA4_RCSS)


def test_stamp_and_identity_bnlt_not_tiktaalik():
    cfg = PhysicalSystemConfig()
    stamp_config_from_preset(cfg, BETA4_TIP)
    assert cfg.model_line == "ACANTHOSTEGA"
    assert cfg.public_preset == BETA4_TIP
    assert bnlt_move_breakaway_locomotion_repair_is_active(cfg)

    meta = identity_from_public_preset(BETA4_TIP, cfg)
    assert meta["model_line"] == "ACANTHOSTEGA"
    assert "Tiktaalik" not in str(meta.get("display_name") or "")

    meta2 = identity_for_config(cfg)
    assert meta2["model_line"] == "ACANTHOSTEGA"
    assert "Tiktaalik" not in str(meta2.get("display_name") or "")


def test_merge_and_preset_canonical_model_line():
    base = preset_canonical(BETA4_TIP, seed=17)
    assert base.get("model_line") == "ACANTHOSTEGA"
    merged = merge_canonical(base, {"public_preset": BETA4_TIP})
    assert merged.get("model_line") == "ACANTHOSTEGA"


def test_observer_apply_bnlt_header_identity():
    sess = ObserverSession()
    out = sess.apply_experiment(
        {
            "public_preset": BETA4_TIP,
            "seed": 17,
            "agent_count": 1,
            "cognition_enabled": False,
            "load_preset": True,
        }
    )
    assert sess.runtime.config.model_line == "ACANTHOSTEGA"
    assert sess.runtime.config.public_preset == BETA4_TIP
    ident = sess.runtime.model_identity()
    assert ident["model_line"] == "ACANTHOSTEGA"
    assert "Tiktaalik" not in str(ident.get("display_name") or "")
    header = out.get("header") or {}
    assert header.get("model_line") == "ACANTHOSTEGA"
    assert "Tiktaalik" not in str(header.get("experiment") or "")
    assert bnlt_move_breakaway_locomotion_repair_is_active(sess.runtime.config)


def test_tiktaalik_preset_still_tiktaalik():
    cfg = PhysicalSystemConfig()
    stamp_config_from_preset(cfg, "TIKTAALIK_BETA31")
    assert cfg.model_line == "TIKTAALIK"
    meta = identity_from_public_preset("TIKTAALIK_BETA31", cfg)
    assert meta["model_line"] == "TIKTAALIK"
