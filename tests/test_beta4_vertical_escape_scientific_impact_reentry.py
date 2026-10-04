"""Impact-resolution tooling tests — no simulation ticks."""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path("results/scientific_impact_resolution_vertical_escape_evidence_reentry")


def _load_jsonl(name: str) -> list[dict]:
    return [json.loads(l) for l in (OUT / name).read_text().splitlines() if l.strip()]


def test_reuse_contract_frozen_before_outcomes():
    c = json.loads((OUT / "PRE_REPAIR_PACKAGE_REUSE_CONTRACT.json").read_text())
    assert c["frozen_before_new_outcomes"] is True
    assert c["total_simulated_ticks_in_seam"] == 0
    assert len(c["reuse_allowed_only_if"]) == 8


def test_body_versus_object_classification_separated():
    s = json.loads((OUT / "PACKAGE_ESCAPE_SUMMARY.json").read_text())
    assert s["s4"]["body_escape_v1b_packages"] == 3
    assert s["s4"]["object_only_packages"] == 26
    assert s["s2"]["body_escape_v1b_packages"] == 0
    assert s["s2"]["object_only_packages"] == 17


def test_finite_support_v1b_defect_not_conflated_with_no_support():
    eps = _load_jsonl("ENTITY_ESCAPE_EPISODES.jsonl")
    v1b = [e for e in eps if e["classification"].endswith("ESCAPE_V1B_DEFECT")]
    assert v1b
    for e in v1b:
        sz = e.get("support_z_at_episode")
        assert sz is not None
        assert float(sz) > -1e150


def test_seed256_body_triad_present():
    s4 = _load_jsonl("S4_PACKAGE_ESCAPE_CLASSIFICATION.jsonl")
    bodies = {r["package"] for r in s4 if r.get("body_escape_v1b")}
    assert bodies == {
        "S4_C1_seed256_t2000",
        "S4_C2_seed256_t2000",
        "S4_C3_seed256_t2000",
    }


def test_matched_group_closure_reruns_all_members():
    m = json.loads((OUT / "MATCHED_GROUP_REENTRY_MATRIX.json").read_text())
    assert m["default_rule"] == "RERUN_ALL_MATCHED"
    assert m["affected_group_count"] >= 5
    for g in m["groups"]:
        if g["action"] == "RERUN_ALL_MATCHED":
            assert g["members"]


def test_no_duplicate_package_rows():
    for name in ("S2_PACKAGE_ESCAPE_CLASSIFICATION.jsonl", "S4_PACKAGE_ESCAPE_CLASSIFICATION.jsonl"):
        rows = _load_jsonl(name)
        pkgs = [r["package"] for r in rows]
        assert len(pkgs) == len(set(pkgs))


def test_old_new_generation_separation():
    reg = json.loads((OUT / "SCIENTIFIC_GENERATION_REGISTRY.json").read_text())
    ids = [g["id"] for g in reg["generations"]]
    assert "GEN_PRE_REPAIR_BETA4_S4_S6" in ids
    assert "GEN_POST_V1B_VERTICAL_SUPPORT_ESCAPE_REPAIR" in ids
    pre = next(g for g in reg["generations"] if g["id"].startswith("GEN_PRE"))
    assert pre["admissible_in_new_confirmatory_inference"] is False
    assert pre["status"] == "SUPERSEDED_PENDING_VERTICAL_ESCAPE_REVALIDATION"


def test_hypothesis_dependency_mapping_complete():
    h = json.loads((OUT / "HYPOTHESIS_VERTICAL_ESCAPE_DEPENDENCY_MATRIX.json").read_text())["hypotheses"]
    for i in range(1, 11):
        assert f"H{i}" in h
        assert h[f"H{i}"]["impact_class"]


def test_recommended_scope_is_full_primary_not_executed():
    r = json.loads((OUT / "RECOMMENDED_REVALIDATION_MANIFEST.json").read_text())
    assert r["scope"] == "B_ALL_PRIMARY_PACKAGES"
    assert r["package_count"] == 40
    assert r["execution_authorized"] is False
    assert r["ticks"] == 80000


def test_storage_projection_pass():
    s = json.loads((OUT / "STORAGE_AND_WALLCLOCK_PROJECTION.json").read_text())
    assert s["storage_capacity_pass"] is True
    assert s["old_evidence_deletion"] == "FORBIDDEN"


def test_idempotent_summary_counts():
    s1 = json.loads((OUT / "PACKAGE_ESCAPE_SUMMARY.json").read_text())
    s4 = _load_jsonl("S4_PACKAGE_ESCAPE_CLASSIFICATION.jsonl")
    assert s1["s4"]["package_count"] == len(s4)
    assert s1["s4"]["body_escape_v1b_packages"] == sum(1 for r in s4 if r.get("body_escape_v1b"))


def test_old_evidence_not_rewritten_markers():
    # Presence of amendment without mutating S6 FINAL_HYPOTHESIS_STATUS_MATRIX values
    old = json.loads(
        Path("results/acanthostega_beta4_s6_scientific_behavioral_closure/FINAL_HYPOTHESIS_STATUS_MATRIX.json").read_text()
    )
    assert "H1" in json.dumps(old)
    assert (OUT / "S6_STATUS_AMENDMENT.md").read_text().count("SUPERSEDED_PENDING_VERTICAL_ESCAPE_REVALIDATION") >= 1
