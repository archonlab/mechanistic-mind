"""VOLUMETRIC_ANALYZER_PHYSICAL_CAUSAL_RECONSTRUCTION_V1

Researcher reconstruction over authoritative physical receipts.
Preserves SCIENTIFIC_V3 TickStories; attaches linked physical causal stories.
Does not create physical authority.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCHEMA = "VOLUMETRIC_ANALYZER_PHYSICAL_CAUSAL_RECONSTRUCTION_V1"
CAPABILITY = "volumetric_analyzer_physical_causal_reconstruction"
PROFILE = "VW1_TO_VW6_MECHANISM_CAUSAL_STORY_V1"
AUTHORITY = "RESEARCHER_RECONSTRUCTION_OVER_AUTHORITATIVE_PHYSICAL_RECEIPTS"
SECTION_TITLE = "VOLUMETRIC PHYSICAL CAUSAL STORY"

LADDER_RUNGS = (
    "OBSERVED",
    "SELECTED",
    "ACTUATED",
    "REACHED",
    "CONTACTED",
    "WORK_TRANSMITTED",
    "FAILURE",
    "OBJECT_CREATED",
    "LATER_MANIPULATION",
    "PERCEPTUAL_CHANGE",
)

NEGATIVE_CLASSES = (
    "NOT_SELECTED",
    "CONTROL_NOT_AVAILABLE",
    "CONTROL_AVAILABILITY_NOT_ESTABLISHED",
    "REQUIRED_CONTROL_NOT_IN_REPERTOIRE",  # legacy alias of CONTROL_NOT_AVAILABLE
    "SELECTED_NOT_ACTUATED",
    "ACTUATED_NO_DISPLACEMENT",
    "ACTUATED_NO_GEOMETRIC_REACH",
    "GEOMETRIC_REACH_NO_CONTACT",
    "CONTACT_NO_WORK",
    "CONTACT_INSUFFICIENT_WORK",
    "CONTACT_SUFFICIENT_WORK_NO_FAILURE",
    "MATERIAL_FAILURE",
    "DETACHED_MATERIAL_CREATED",
    "DETACHED_OBJECT_CREATED",  # legacy alias
    "POST_FAILURE_MANIPULATION_NOT_ESTABLISHED",
    "FAILED_WITH_OBSERVED_CAUSE",
    "SUCCESS",
    "NOT_AVAILABLE",
    "NOT_ESTABLISHED",
)

CONTROL_AVAIL_AVAILABLE = "AVAILABLE"
CONTROL_AVAIL_UNAVAILABLE = "UNAVAILABLE"
CONTROL_AVAIL_NOT_ESTABLISHED = "NOT_ESTABLISHED"

Z_FIELD_LEFT = "effector_z_left"
Z_FIELD_RIGHT = "effector_z_right"
Z_FIELD_ALIASES_LEFT = (Z_FIELD_LEFT, "left_effector_z", "effector_z_L")
Z_FIELD_ALIASES_RIGHT = (Z_FIELD_RIGHT, "right_effector_z", "effector_z_R")
EBAE_KIND_ALIASES = (
    "effector_bounded_actuator_effort",
    "EFFECTOR_ACTUATOR_EFFORT",
    "EFFECTOR_ACTUATOR_EFFORT_STEP",
)


def _rung(status: str, cause: str | None = None) -> dict[str, Any]:
    return {"status": status, "observed_cause": cause}


def _model_authority(run_dir: Path) -> dict[str, Any]:
    """Derive model/world authority from run metadata without inventing volumetric claims."""
    public_preset = None
    model_line = None
    for name in ("run.json", "scientific_meta.json", "scientific_v3_meta.json"):
        p = Path(run_dir) / name
        if not p.is_file():
            continue
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(raw, dict):
            continue
        public_preset = public_preset or raw.get("public_preset") or (raw.get("model") or {}).get(
            "public_preset"
        )
        model_line = model_line or raw.get("model_line") or (raw.get("model") or {}).get("model_line")
        cfg = raw.get("config") if isinstance(raw.get("config"), dict) else {}
        public_preset = public_preset or cfg.get("public_preset")
        model_line = model_line or cfg.get("model_line")
    preset_s = str(public_preset or "")
    line_s = str(model_line or "")
    is_beta4 = (
        "ACANTHOSTEGA_BETA4" in preset_s
        or "BETA4" in preset_s.upper()
        or ("ACANTHOSTEGA" in line_s.upper() and "BETA4" in preset_s.upper())
    )
    is_tiktaalik = "TIKTAALIK" in line_s.upper() or "TIKTAALIK" in preset_s.upper()
    if is_beta4 or ("ACANTHOSTEGA" in line_s.upper() and "BETA3" not in preset_s.upper()):
        # Prefer explicit beta4; also treat ACANTHOSTEGA model_line with VW evidence as volumetric-capable.
        world = {
            "world_dimensionality": "VOLUMETRIC_XYZ",
            "vw1_occupancy_authority": "AVAILABLE_WHEN_RECEIPTS_PRESENT",
            "described_as_2d": False,
            "volumetric_physical_story": "APPLICABLE",
            "legacy_xy_only": False,
        }
    elif is_tiktaalik:
        world = {
            "world_dimensionality": "LEGACY_XY",
            "vw1_occupancy_authority": "NOT_APPLICABLE",
            "described_as_2d": True,
            "volumetric_physical_story": "NOT_APPLICABLE",
            "legacy_xy_only": True,
        }
    else:
        world = {
            "world_dimensionality": "NOT_ESTABLISHED",
            "vw1_occupancy_authority": "NOT_ESTABLISHED",
            "described_as_2d": False,
            "volumetric_physical_story": "DERIVE_FROM_EVIDENCE",
            "legacy_xy_only": False,
        }
    return {
        "public_preset": public_preset,
        "model_line": model_line,
        "is_acanthostega_beta4": bool(is_beta4 or (line_s == "ACANTHOSTEGA" and "BETA4" in preset_s)),
        "is_tiktaalik": bool(is_tiktaalik),
        **world,
    }


def _normalize_receipt_kind(kind: str, receipt_kind: str | None = None) -> str:
    raw = str(kind or receipt_kind or "").strip()
    if raw in EBAE_KIND_ALIASES or "ACTUATOR_EFFORT" in raw.upper() or "bounded_actuator" in raw.lower():
        return "effector_bounded_actuator_effort"
    if "REACHABILITY" in raw.upper():
        return "effector_occupancy_reachability_trace"
    if raw in ("effector_terrain_contact",) or "TERRAIN_CONTACT" in raw.upper() and "HELD" not in raw.upper():
        return "effector_terrain_contact"
    if "WORLD_MATERIAL" in raw.upper() or raw == "world_material_transaction":
        return "world_material_transaction"
    return raw


def index_physical_receipts_from_consequences(run_dir: Path | str) -> dict[str, list[dict[str, Any]]]:
    """One-pass index of physical event_refs by kind from consequence JSONL."""
    path = Path(run_dir) / "scientific_consequences.jsonl"
    alt = Path(run_dir) / "consequences.jsonl"
    path = path if path.is_file() else alt
    by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not path.is_file():
        return by_kind
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        tick = row.get("tick")
        if tick is None:
            tick = row.get("tick_from")
        agent = row.get("cognitive_agent_id") or row.get("agent_id")
        body = row.get("physical_body_id") or row.get("body_id")
        gen = row.get("generation") or row.get("runtime_generation")
        for ref in row.get("event_refs") or []:
            if not isinstance(ref, dict):
                continue
            kind = _normalize_receipt_kind(
                str(ref.get("kind") or ""),
                str(ref.get("receipt_kind") or "") or None,
            )
            if not kind:
                continue
            item = dict(ref)
            item["_cons_tick"] = tick
            item["_agent_id"] = agent
            item["_body_id"] = body
            if gen is not None:
                item.setdefault("_generation", gen)
            by_kind[kind].append(item)
            # Also keep original kind bucket for diagnostics.
            orig = str(ref.get("kind") or "")
            if orig and orig != kind:
                by_kind[orig].append(item)
    return by_kind


def _motor_components(story: Any) -> dict[str, Any]:
    mot = getattr(story, "motor", None)
    if not isinstance(mot, dict):
        return {}
    comps = mot.get("components")
    if isinstance(comps, dict):
        return comps
    return mot


def _normalize_z_request(comps: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    """Return -1/0/+1 or NOT_AVAILABLE if field absent."""
    present = False
    val = 0
    for k in aliases:
        if k in comps:
            present = True
            try:
                val = int(comps.get(k) or 0)
            except (TypeError, ValueError):
                val = 0
            break
    if not present:
        return "NOT_AVAILABLE"
    if val > 0:
        return 1
    if val < 0:
        return -1
    return 0


def derive_control_availability(
    *,
    model: dict[str, Any],
    comps: dict[str, Any],
    traces: list[dict[str, Any]],
    motor_schema: str | None = None,
) -> tuple[str, str]:
    """Return (AVAILABLE|UNAVAILABLE|NOT_ESTABLISHED, authority_source)."""
    if model.get("volumetric_physical_story") == "NOT_APPLICABLE" or model.get("is_tiktaalik"):
        return CONTROL_AVAIL_UNAVAILABLE, "model_authority:legacy_or_tiktaalik"
    if model.get("z_control_enabled") is True or model.get("effector_relative_z_enabled") is True:
        return CONTROL_AVAIL_AVAILABLE, "config_capability_declaration"
    left_present = any(k in comps for k in Z_FIELD_ALIASES_LEFT)
    right_present = any(k in comps for k in Z_FIELD_ALIASES_RIGHT)
    if left_present or right_present:
        return CONTROL_AVAIL_AVAILABLE, "motor_receipt_schema:effector_z_*"
    if motor_schema and "COMPOSITE_MOTOR" in str(motor_schema).upper() and model.get("is_acanthostega_beta4"):
        # Composite schema without Z fields on this receipt → not established (do not invent).
        return CONTROL_AVAIL_NOT_ESTABLISHED, "composite_motor_without_z_fields"
    if traces:
        sel = str(traces[0].get("agent_selectable_motor_factor") or "")
        if sel == "PRESENT":
            return CONTROL_AVAIL_AVAILABLE, "reachability_trace:agent_selectable_motor_factor=PRESENT"
        if sel == "ABSENT":
            return CONTROL_AVAIL_UNAVAILABLE, "reachability_trace:agent_selectable_motor_factor=ABSENT"
    if model.get("control_explicitly_absent") is True:
        return CONTROL_AVAIL_UNAVAILABLE, "explicit_absence_marker"
    return CONTROL_AVAIL_NOT_ESTABLISHED, "insufficient_legacy_evidence"


def _aligned_pose_delta(
    traces: list[dict[str, Any]],
    *,
    pose_by_key: dict[tuple[str, str, str], list[tuple[int, float]]] | None,
    body: str,
    generation: str,
) -> dict[str, Any]:
    """Generation-safe consecutive pose delta for effectors present this tick."""
    out: dict[str, Any] = {
        "effectors": {},
        "any_nonzero_delta": False,
        "authority": "consecutive_compatible_traces",
    }
    if not pose_by_key or not traces:
        out["authority"] = "unavailable"
        return out
    for t in traces:
        eff = str(t.get("effector_id") or "")
        if not eff:
            continue
        from .tick_normalize import coerce_tick

        tick = coerce_tick(t.get("tick", t.get("_cons_tick")), default=-1)
        if tick is None:
            tick = -1
        tick = int(tick)
        try:
            rz_after = float(t.get("relative_z") or 0.0)
        except (TypeError, ValueError):
            continue
        key = (str(generation), str(body), eff)
        series = pose_by_key.get(key) or []
        rz_before = None
        for pt, prz in reversed(series):
            if pt < tick:
                rz_before = prz
                break
            if pt == tick:
                # find prior
                continue
        if rz_before is None:
            out["effectors"][eff] = {
                "relative_z_before": None,
                "relative_z_after": rz_after,
                "delta_relative_z": None,
                "status": "NO_PRIOR_COMPATIBLE_TRACE",
            }
            continue
        delta = float(rz_after) - float(rz_before)
        nonzero = abs(delta) > 1e-15
        if nonzero:
            out["any_nonzero_delta"] = True
        out["effectors"][eff] = {
            "relative_z_before": rz_before,
            "relative_z_after": rz_after,
            "delta_relative_z": delta,
            "status": "OK",
        }
    return out


def _ebae_for_story(
    ebae_rows: list[dict[str, Any]],
    *,
    tick: int,
    body: str,
) -> list[dict[str, Any]]:
    out = []
    for r in ebae_rows:
        rt = int(r.get("tick", r.get("_cons_tick", -2)) or -2)
        if rt != tick:
            continue
        bid = str(r.get("body_id") or r.get("_body_id") or "")
        if body and bid and bid not in ("", body):
            continue
        out.append(r)
    return out


def _ebae_acceptance(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize EBAE request/accept/displacement from receipts."""
    if not rows:
        return {
            "present": False,
            "submitted": False,
            "accepted": False,
            "rejected": False,
            "applied_nonzero": False,
            "applied_zero": False,
            "work_debit": 0.0,
            "reasons": [],
        }
    submitted = True
    accepted = False
    rejected = False
    applied_nz = False
    applied_zero = False
    work = 0.0
    reasons: list[str] = []
    for r in rows:
        st = str(r.get("status") or "").upper()
        try:
            ach = float(r.get("achieved_relative_delta") if r.get("achieved_relative_delta") is not None else r.get("delta_relative_z") or 0.0)
        except (TypeError, ValueError):
            ach = 0.0
        try:
            work = max(work, float(r.get("work_used") or 0.0))
        except (TypeError, ValueError):
            pass
        if st in ("REJECTED", "DENIED", "CAPABILITY_OFF", "UNAVAILABLE"):
            rejected = True
            reasons.append(st)
        elif st in ("FREE_SPACE", "EXTERNAL_BLOCK", "PARTIAL_BLOCK", "FULLY_BLOCKED", "OK", "APPLIED", "ACCEPTED"):
            accepted = True
        else:
            # Unknown status but receipt present → treat as submitted; accept if delta defined
            accepted = True
        if abs(ach) > 1e-15:
            applied_nz = True
        else:
            applied_zero = True
            if st:
                reasons.append(st)
    return {
        "present": True,
        "submitted": submitted,
        "accepted": accepted and not (rejected and not accepted),
        "rejected": rejected and not accepted,
        "applied_nonzero": applied_nz,
        "applied_zero": applied_zero and not applied_nz,
        "work_debit": work,
        "reasons": reasons,
        "receipt_count": len(rows),
    }


def _motor_token(story: Any) -> str | None:
    m = getattr(story, "motor", None) or {}
    if not isinstance(m, dict):
        return None
    for k in ("selected_action", "action", "composite_summary", "motor_token"):
        if m.get(k):
            return str(m.get(k))
    factors = m.get("factors") or m.get("composite_factors")
    if isinstance(factors, dict):
        return json.dumps(factors, sort_keys=True, default=str)
    return None


def _normalize_derived_changes(raw: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Canonicalize TickStory.derived_changes into a list of dict records.

    Accepts:
      - list of dicts (authoritative TickStory shape)
      - single dict (legacy mistaken envelope)
      - None / empty
    Never silently swallows malformed elements as empty evidence without warning.
    """
    warnings: list[str] = []
    if raw is None:
        return [], warnings
    if isinstance(raw, list):
        out: list[dict[str, Any]] = []
        for i, item in enumerate(raw):
            if isinstance(item, dict):
                out.append(item)
            else:
                warnings.append(f"derived_changes[{i}]_not_dict:{type(item).__name__}")
        return out, warnings
    if isinstance(raw, dict):
        # Legacy mistaken envelope: either already a POSE-like dict, or keyed records.
        if raw.get("kind") or ("x" in raw or "z" in raw):
            return [raw], ["derived_changes_was_single_dict"]
        records = []
        for k, v in raw.items():
            if isinstance(v, dict):
                row = dict(v)
                row.setdefault("kind", str(k))
                records.append(row)
            else:
                warnings.append(f"derived_changes[{k}]_not_dict:{type(v).__name__}")
        return records, ["derived_changes_was_dict_envelope"]
    warnings.append(f"derived_changes_unexpected_type:{type(raw).__name__}")
    return [], warnings


def _pose_record_from_derived(derived: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Extract POSE_STATE (or pose-like) record from normalized derived_changes."""
    for d in derived:
        if str(d.get("kind") or "") == "POSE_STATE":
            return d
    for d in derived:
        if d.get("x") is not None or d.get("z") is not None or d.get("centre_z") is not None:
            return d
    return None


def _body_xyz_from_story(story: Any) -> dict[str, Any]:
    raw_derived = getattr(story, "derived_changes", None)
    derived, _warnings = _normalize_derived_changes(raw_derived)
    cons = getattr(story, "consequence", None) or {}
    if not isinstance(cons, dict):
        cons = {}
    pose = _pose_record_from_derived(derived) or {}
    # Consequence receipts use pose_delta / support fields — not a nested "pose" key.
    pose_delta = cons.get("pose_delta") if isinstance(cons.get("pose_delta"), dict) else {}
    out = {
        "body_base_xyz": None,
        "body_centre_xyz": None,
        "delta_xyz": None,
        "support_state": None,
        "support_source": None,
        "status": "NOT_AVAILABLE",
    }
    x = pose.get("x")
    y = pose.get("y")
    z = pose.get("z")
    cz = pose.get("centre_z")
    if x is not None or y is not None or z is not None or cz is not None:
        out["body_base_xyz"] = [x, y, z]
        out["body_centre_xyz"] = [x, y, cz] if cz is not None else None
        out["delta_xyz"] = pose.get("delta_xyz") or (
            {"dx": pose_delta.get("dx"), "dy": pose_delta.get("dy")}
            if pose_delta
            else None
        )
        out["support_state"] = pose.get("grounded") or pose.get("support_state")
        out["support_source"] = pose.get("support_z") or pose.get("support_source")
        out["status"] = "YES" if z is not None or cz is not None else "PARTIAL"
    elif pose_delta:
        out["delta_xyz"] = {"dx": pose_delta.get("dx"), "dy": pose_delta.get("dy")}
        out["status"] = "PARTIAL"
    # Free-space / vertical receipts may appear in external_context
    for ctx in getattr(story, "external_context", None) or []:
        if not isinstance(ctx, dict):
            continue
        if ctx.get("kind") in ("free_space_support", "vertical_landing", "flat_ground_gravity"):
            out["support_state"] = out["support_state"] or ctx.get("support_state") or ctx.get("grounded")
            out["support_source"] = out["support_source"] or ctx.get("support_z") or ctx.get("boundary_z")
            if out["status"] == "NOT_AVAILABLE":
                out["status"] = "PARTIAL"
    return out


def classify_story_physical(
    story: Any,
    *,
    reach_traces: list[dict[str, Any]],
    etc_contacts: list[dict[str, Any]],
    work_rows: list[dict[str, Any]],
    wmt_rows: list[dict[str, Any]],
    model: dict[str, Any],
    ebae_rows: list[dict[str, Any]] | None = None,
    pose_by_key: dict[tuple[str, str, str], list[tuple[int, float]]] | None = None,
    runtime_generation: str | int | None = None,
) -> dict[str, Any]:
    """Build one linked physical causal story for a TickStory."""
    from .tick_normalize import normalize_story_tick

    _tick = normalize_story_tick(story)
    tick = int(_tick) if _tick is not None else -1
    agent = str(getattr(story, "cognitive_agent_id", "") or "")
    body = str(getattr(story, "physical_body_id", "") or "")
    motor = _motor_token(story)
    gen = str(
        runtime_generation
        if runtime_generation is not None
        else getattr(story, "generation", None) or model.get("runtime_generation") or model.get("generation") or "0"
    )

    if model.get("volumetric_physical_story") == "NOT_APPLICABLE":
        return {
            "schema": SCHEMA,
            "tick": tick,
            "cognitive_agent_id": agent,
            "physical_body_id": body,
            "status": "NOT_APPLICABLE",
            "model_authority": model,
            "negative_cause": "NOT_AVAILABLE",
            "control_availability": CONTROL_AVAIL_UNAVAILABLE,
            "causal_ladder": {r: _rung("NOT_APPLICABLE") for r in LADDER_RUNGS},
            "linked_tick_story": True,
        }

    body_xyz = _body_xyz_from_story(story)
    traces = [
        t
        for t in reach_traces
        if int(t.get("tick", t.get("_cons_tick", -2)) or -2) == tick
        and (not body or str(t.get("body_id") or t.get("_body_id") or "") in ("", body))
    ]
    contacts = [
        c
        for c in etc_contacts
        if int(c.get("tick", c.get("_cons_tick", -2)) or -2) == tick
        and (not body or str(c.get("body_id") or c.get("_body_id") or "") in ("", body))
        and c.get("contact_fact")
    ]
    works = [
        w
        for w in work_rows
        if int(w.get("tick", w.get("_cons_tick", -2)) or -2) == tick
    ]
    wmts = [
        w
        for w in wmt_rows
        if int(w.get("tick", w.get("_cons_tick", -2)) or -2) == tick
    ]
    ebae = _ebae_for_story(list(ebae_rows or []), tick=tick, body=body)
    # Also accept EBAE-shaped rows mixed into work_rows
    for w in works:
        rk = _normalize_receipt_kind(str(w.get("kind") or ""), str(w.get("receipt_kind") or "") or None)
        if rk == "effector_bounded_actuator_effort" and w not in ebae:
            ebae.append(w)

    comps = _motor_components(story)
    mot_obj = getattr(story, "motor", None) if isinstance(getattr(story, "motor", None), dict) else {}
    motor_schema = str(mot_obj.get("motor_schema") or comps.get("motor_schema") or "")
    left_z = _normalize_z_request(comps, Z_FIELD_ALIASES_LEFT)
    right_z = _normalize_z_request(comps, Z_FIELD_ALIASES_RIGHT)
    z_request_nonzero = any(isinstance(v, int) and v != 0 for v in (left_z, right_z))
    z_fields_present = left_z != "NOT_AVAILABLE" or right_z != "NOT_AVAILABLE"

    control_avail, control_authority = derive_control_availability(
        model=model, comps=comps, traces=traces, motor_schema=motor_schema or None
    )
    # Zero-valued Z fields mean AVAILABLE (NONE selected), never UNAVAILABLE.
    if z_fields_present and control_avail != CONTROL_AVAIL_UNAVAILABLE:
        control_avail = CONTROL_AVAIL_AVAILABLE
        if "motor_receipt_schema" not in control_authority:
            control_authority = "motor_receipt_schema:effector_z_*"

    pose_delta = _aligned_pose_delta(traces, pose_by_key=pose_by_key, body=body, generation=gen)
    ebae_sum = _ebae_acceptance(ebae)
    # Actuation evidence: NEVER |pose relative_z| alone.
    actuated = bool(
        ebae_sum["accepted"]
        or ebae_sum["applied_nonzero"]
        or (z_request_nonzero and pose_delta.get("any_nonzero_delta"))
    )
    actuated_zero_disp = bool(
        ebae_sum["accepted"] and ebae_sum["applied_zero"] and not ebae_sum["applied_nonzero"]
    )
    geometric_reach = any(bool(t.get("geometric_reach")) for t in traces)
    work_used = max(
        (float(w.get("work_used") or w.get("work_transmitted_to_terrain") or 0.0) for w in works),
        default=0.0,
    )
    work_positive = work_used > 0.0
    failure = any(
        bool(w.get("material_failure") or w.get("failure") or str(w.get("status") or "").upper() == "FAILURE")
        for w in wmts + works
    )
    object_created = any(
        bool(w.get("object_id") or w.get("detached_object_id") or w.get("created_object_id"))
        for w in wmts
    )

    missing: list[str] = []
    if not ebae_sum["present"] and z_request_nonzero:
        missing.append("EBAE_EVENT_REF_ABSENT")
    if pose_delta.get("authority") == "unavailable":
        missing.append("POSE_DELTA_UNAVAILABLE")

    # Mutually exclusive taxonomy (contact/failure first when those facts exist).
    if object_created:
        neg = "DETACHED_MATERIAL_CREATED"
    elif failure:
        neg = "MATERIAL_FAILURE"
    elif contacts and not work_positive:
        neg = "CONTACT_INSUFFICIENT_WORK"
    elif contacts and work_positive and not failure:
        neg = "CONTACT_INSUFFICIENT_WORK"
    elif contacts and geometric_reach is False:
        neg = "CONTACT_INSUFFICIENT_WORK"
    elif control_avail == CONTROL_AVAIL_UNAVAILABLE and not z_request_nonzero and not contacts:
        neg = "CONTROL_NOT_AVAILABLE"
    elif control_avail == CONTROL_AVAIL_NOT_ESTABLISHED and not z_request_nonzero and not contacts:
        neg = "CONTROL_AVAILABILITY_NOT_ESTABLISHED"
    elif control_avail == CONTROL_AVAIL_AVAILABLE and not z_request_nonzero and not contacts:
        neg = "NOT_SELECTED"
    elif z_request_nonzero and not actuated and not actuated_zero_disp and not contacts:
        neg = "SELECTED_NOT_ACTUATED"
    elif z_request_nonzero and actuated_zero_disp and not contacts:
        neg = "ACTUATED_NO_DISPLACEMENT"
    elif z_request_nonzero and actuated and not geometric_reach and not contacts:
        neg = "ACTUATED_NO_GEOMETRIC_REACH"
    elif z_request_nonzero and actuated and geometric_reach and not contacts:
        neg = "GEOMETRIC_REACH_NO_CONTACT"
    elif traces:
        neg = "NOT_ESTABLISHED"
    else:
        neg = "NOT_AVAILABLE" if model.get("volumetric_physical_story") != "APPLICABLE" else "NOT_ESTABLISHED"

    # Legacy alias for forbidden-token / older UI recognition
    legacy_alias = "REQUIRED_CONTROL_NOT_IN_REPERTOIRE" if neg == "CONTROL_NOT_AVAILABLE" else None

    agent_sel_factor = (
        "PRESENT" if control_avail == CONTROL_AVAIL_AVAILABLE
        else ("ABSENT" if control_avail == CONTROL_AVAIL_UNAVAILABLE else "NOT_ESTABLISHED")
    )
    control = {
        "physical_relative_z_dof": (
            traces[0].get("physical_relative_z_dof") if traces else (
                "AVAILABLE" if control_avail == CONTROL_AVAIL_AVAILABLE else control_avail
            )
        ),
        "research_actuator_path": traces[0].get("research_actuator_path") if traces else "AVAILABLE",
        "agent_cognition_token": traces[0].get("agent_cognition_token") if traces else (
            "PRESENT" if control_avail == CONTROL_AVAIL_AVAILABLE else "ABSENT"
        ),
        "agent_selectable_motor_factor": agent_sel_factor,
        "control_availability": control_avail,
        "control_availability_authority": control_authority,
        "selected_motor": motor,
        "left_z_request": left_z,
        "right_z_request": right_z,
        "z_request_nonzero": z_request_nonzero,
        "effector_z_factors": [
            v for v in (left_z, right_z) if isinstance(v, int)
        ],
        "relative_z_values": sorted({float(t.get("relative_z") or 0.0) for t in traces}),
        "pose_delta": pose_delta,
        "ebae": ebae_sum,
        "missing_evidence": missing,
        "actuation_authority": (
            "EBAE_RECEIPT" if ebae_sum["present"]
            else ("MOTOR_REQUEST_PLUS_ALIGNED_POSE_DELTA" if (z_request_nonzero and pose_delta.get("any_nonzero_delta"))
                  else ("MOTOR_REQUEST_ONLY" if z_request_nonzero else "NONE"))
        ),
        # Explicit: pose magnitude alone is never actuation.
        "pose_relative_z_used_as_actuation": False,
    }

    ladder = {
        "OBSERVED": _rung("YES" if getattr(story, "observation_id", None) else "NOT_AVAILABLE"),
        "SELECTED": _rung(
            "YES" if z_request_nonzero else (
                "NO_WITH_OBSERVED_CAUSE" if control_avail == CONTROL_AVAIL_AVAILABLE else "NOT_ESTABLISHED"
            ),
            neg if not z_request_nonzero else None,
        ),
        "ACTUATED": _rung(
            "YES" if actuated else (
                "NO_WITH_OBSERVED_CAUSE" if neg in (
                    "CONTROL_NOT_AVAILABLE", "NOT_SELECTED", "SELECTED_NOT_ACTUATED", "ACTUATED_NO_DISPLACEMENT"
                ) else "NOT_ESTABLISHED"
            ),
            neg if not actuated else None,
        ),
        "REACHED": _rung(
            "YES" if geometric_reach else (
                "NO_WITH_OBSERVED_CAUSE" if neg in (
                    "CONTROL_NOT_AVAILABLE", "ACTUATED_NO_GEOMETRIC_REACH", "NOT_SELECTED", "SELECTED_NOT_ACTUATED"
                ) else "NOT_ESTABLISHED"
            ),
            None if geometric_reach else neg,
        ),
        "CONTACTED": _rung("YES" if contacts else "NO_WITH_OBSERVED_CAUSE", None if contacts else neg),
        "WORK_TRANSMITTED": _rung(
            "YES" if work_positive else ("NO_WITH_OBSERVED_CAUSE" if contacts else "NOT_ESTABLISHED"),
            None if work_positive else (neg if contacts else None),
        ),
        "FAILURE": _rung(
            "YES" if failure else "NO_WITH_OBSERVED_CAUSE",
            None if failure else ("CONTACT_INSUFFICIENT_WORK" if work_positive else None),
        ),
        "OBJECT_CREATED": _rung("YES" if object_created else "NOT_ESTABLISHED"),
        "LATER_MANIPULATION": _rung("NOT_ESTABLISHED"),
        "PERCEPTUAL_CHANGE": _rung("NOT_ESTABLISHED"),
    }

    min_sep = None
    seps = [t.get("signed_minimum_separation") for t in traces if t.get("signed_minimum_separation") is not None]
    if seps:
        min_sep = min(float(s) for s in seps)

    notes = [
        f"control_availability={control_avail} authority={control_authority}",
        f"left_z_request={left_z} right_z_request={right_z}",
        f"actuation_authority={control['actuation_authority']}",
        "Pose |relative_z| alone is never treated as current-tick actuation.",
    ]
    if missing:
        notes.append("missing_evidence=" + ",".join(missing))
    if legacy_alias:
        notes.append(f"legacy_alias={legacy_alias}")

    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "tick": tick,
        "cognitive_agent_id": agent,
        "physical_body_id": body,
        "runtime_generation": gen,
        "observation_id": getattr(story, "observation_id", None),
        "decision_id": getattr(story, "decision_id", None),
        "motor_id": getattr(story, "motor_id", None),
        "consequence_id": getattr(story, "consequence_id", None),
        "linked_tick_story": True,
        "model_authority": {
            "public_preset": model.get("public_preset"),
            "model_line": model.get("model_line"),
            "world_dimensionality": model.get("world_dimensionality"),
            "described_as_2d": bool(model.get("described_as_2d")),
        },
        "body_xyz": body_xyz,
        "control_availability": control_avail,
        "control_repertoire": control,
        "reachability": {
            "trace_count": len(traces),
            "trace_ids": [t.get("trace_id") for t in traces if t.get("trace_id")],
            "geometric_reach": geometric_reach,
            "min_signed_separation": min_sep,
            "effectors": sorted({str(t.get("effector_id")) for t in traces if t.get("effector_id")}),
        },
        "contact": {
            "contact_fact_count": len(contacts),
            "episode_ids": [c.get("episode_id") for c in contacts if c.get("episode_id")],
            "distinct_from_work": True,
        },
        "work_resistance": {
            "work_used_max": work_used,
            "work_positive": work_positive,
            "failure_observed": failure,
            "distinct_from_failure": True,
            "held_to_world_trigger": "BLOCKED",
        },
        "occupancy_object": {
            "wmt_count": len(wmts),
            "detached_object_created": object_created,
            "vw4_reintegration": "NOT_ESTABLISHED",
        },
        "perception": {
            "status": "NOT_ESTABLISHED",
            "causal_influence_on_selection": "NOT_ESTABLISHED",
        },
        "negative_cause": neg,
        "legacy_negative_cause_alias": legacy_alias,
        "causal_ladder": ladder,
        "notes": notes,
        "researcher_only": True,
        "cognition_exposed": False,
    }


def _build_pose_series(
    reach: list[dict[str, Any]],
    *,
    generation: str,
) -> dict[tuple[str, str, str], list[tuple[int, float]]]:
    """Map (generation, body_id, effector_id) → sorted (tick, relative_z)."""
    buckets: dict[tuple[str, str, str], list[tuple[int, float]]] = defaultdict(list)
    for t in reach:
        body = str(t.get("body_id") or t.get("_body_id") or "")
        eff = str(t.get("effector_id") or "")
        if not body or not eff:
            continue
        from .tick_normalize import coerce_tick

        tick = coerce_tick(t.get("tick", t.get("_cons_tick")), default=-1)
        if tick is None:
            tick = -1
        tick = int(tick)
        try:
            rz = float(t.get("relative_z") or 0.0)
        except (TypeError, ValueError):
            continue
        gen = str(t.get("_generation") or t.get("generation") or generation)
        buckets[(gen, body, eff)].append((tick, rz))
    for key in buckets:
        buckets[key].sort(key=lambda x: x[0])
    return buckets


def build_volumetric_physical_causal_reconstruction(
    stories: list[Any],
    *,
    run_dir: Path | str,
    on_progress: Any | None = None,
) -> dict[str, Any]:
    run_dir = Path(run_dir)
    if on_progress:
        on_progress("INDEX_PHYSICAL_RECEIPTS", 0, len(stories))
    model = _model_authority(run_dir)
    gen = "0"
    for name in ("scientific_v3_meta.json", "scientific_meta.json", "identity_map.json"):
        pth = run_dir / name
        if not pth.is_file():
            continue
        try:
            raw = json.loads(pth.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(raw, dict) and raw.get("generation") is not None:
            gen = str(raw.get("generation"))
            model["runtime_generation"] = gen
            break

    by_kind = index_physical_receipts_from_consequences(run_dir)
    reach = by_kind.get("effector_occupancy_reachability_trace") or []
    etc = by_kind.get("effector_terrain_contact") or []
    ebae_rows = list(by_kind.get("effector_bounded_actuator_effort") or [])
    work_rows = list(ebae_rows)
    for k in (
        "held_resource_object_terrain_mechanical_transmission",
        "held_mediated_surface_exertion_integration",
        "surface_exertion_terrain_material_resistance",
    ):
        work_rows.extend(by_kind.get(k) or [])
    wmt = by_kind.get("world_material_transaction") or []
    pose_by_key = _build_pose_series(reach, generation=gen)

    if on_progress:
        on_progress("LINK_REACH_CONTACT", 0, len(stories))

    physical_stories: list[dict[str, Any]] = []
    class_counts: Counter[str] = Counter()
    avail_counts: Counter[str] = Counter()
    z_sel = 0
    ebae_present_stories = 0
    displacement_aligned = 0
    for i, s in enumerate(stories):
        ps = classify_story_physical(
            s,
            reach_traces=reach,
            etc_contacts=etc,
            work_rows=work_rows,
            wmt_rows=wmt,
            model=model,
            ebae_rows=ebae_rows,
            pose_by_key=pose_by_key,
            runtime_generation=gen,
        )
        physical_stories.append(ps)
        class_counts[str(ps.get("negative_cause"))] += 1
        avail_counts[str(ps.get("control_availability") or "NOT_ESTABLISHED")] += 1
        cr = ps.get("control_repertoire") or {}
        if cr.get("z_request_nonzero"):
            z_sel += 1
        if (cr.get("ebae") or {}).get("present"):
            ebae_present_stories += 1
        if (cr.get("pose_delta") or {}).get("any_nonzero_delta") and cr.get("z_request_nonzero"):
            displacement_aligned += 1
        if on_progress and i % 50 == 0:
            on_progress("CLASSIFY_NEGATIVE_CAUSES", i + 1, len(stories))

    if model.get("volumetric_physical_story") == "NOT_APPLICABLE":
        agg_avail = CONTROL_AVAIL_UNAVAILABLE
        avail_authority = "model_not_applicable"
        agent_selectable = "NOT_APPLICABLE"
        relative_z_outcome = "NOT_APPLICABLE"
    else:
        if avail_counts.get(CONTROL_AVAIL_AVAILABLE, 0) > 0:
            agg_avail = CONTROL_AVAIL_AVAILABLE
            avail_authority = "motor_receipt_schema_or_trace"
        elif avail_counts.get(CONTROL_AVAIL_UNAVAILABLE, 0) > 0 and avail_counts.get(CONTROL_AVAIL_AVAILABLE, 0) == 0:
            agg_avail = CONTROL_AVAIL_UNAVAILABLE
            avail_authority = "explicit_absence_or_legacy"
        else:
            agg_avail = CONTROL_AVAIL_NOT_ESTABLISHED
            avail_authority = "insufficient_evidence"
        agent_selectable = (
            "YES" if agg_avail == CONTROL_AVAIL_AVAILABLE
            else ("NO" if agg_avail == CONTROL_AVAIL_UNAVAILABLE else "NOT_ESTABLISHED")
        )
        relative_z_outcome = class_counts.most_common(1)[0][0] if class_counts else "NOT_ESTABLISHED"

    orphan_kinds = {
        k: len(v)
        for k, v in by_kind.items()
        if k
        not in (
            "effector_occupancy_reachability_trace",
            "effector_terrain_contact",
            "world_material_transaction",
            "effector_bounded_actuator_effort",
        )
    }

    relative_z = {
        "physical_dof": "AVAILABLE" if model.get("volumetric_physical_story") != "NOT_APPLICABLE" else "NOT_APPLICABLE",
        "control_availability": agg_avail,
        "control_availability_authority": avail_authority,
        "agent_selectable": agent_selectable,
        "outcome_class": relative_z_outcome,
        "morphological_ground_reachability": "YES" if model.get("volumetric_physical_story") != "NOT_APPLICABLE" else "NOT_APPLICABLE",
        "autonomous_ground_contact_selectable": agent_selectable,
        "z_request_nonzero_count": z_sel,
        "ebae_receipt_story_count": ebae_present_stories,
        "ebae_event_refs_indexed": len(ebae_rows),
        "aligned_displacement_with_z_request_count": displacement_aligned,
        "pose_relative_z_used_as_actuation": False,
        "availability_counts": dict(sorted(avail_counts.items())),
        "limitations": [
            lim
            for lim in (
                "EBAE_EVENT_REFS_ABSENT_IN_HISTORICAL_EVIDENCE" if not ebae_rows else None,
                "PARTIAL_INFERENCE_MOTOR_PLUS_POSE_DELTA" if z_sel and not ebae_rows else None,
            )
            if lim
        ],
    }

    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "section": SECTION_TITLE,
        "status": "AVAILABLE" if model.get("volumetric_physical_story") != "NOT_APPLICABLE" else "NOT_APPLICABLE",
        "model_authority": model,
        "acanthostega_described_as_2d": False if not model.get("described_as_2d") else True,
        "physical_stories_count": len(physical_stories),
        "physical_stories": physical_stories[:500],
        "negative_cause_counts": dict(sorted(class_counts.items())),
        "relative_z": relative_z,
        "receipt_index_counts": {k: len(v) for k, v in sorted(by_kind.items())},
        "orphan_receipt_kinds_sample": dict(list(orphan_kinds.items())[:20]),
        "held_to_world_trigger_status": "BLOCKED",
        "passive_reachability_trace_present": bool(reach),
        "second_contact_solver_created": False,
        "existing_tickstories_preserved": True,
        "scientific_v3_replaced": False,
        "researcher_only": True,
        "cognition_exposed": False,
        "progress_phases": [
            "LOAD_EVIDENCE",
            "BUILD_TICK_STORIES",
            "INDEX_PHYSICAL_RECEIPTS",
            "LINK_ACTION_ACTUATION",
            "LINK_REACH_CONTACT",
            "LINK_WORK_RESISTANCE",
            "LINK_OCCUPANCY_OBJECT",
            "LINK_PERCEPTION",
            "CLASSIFY_NEGATIVE_CAUSES",
            "FINALIZE_STORIES",
        ],
    }


def format_volumetric_physical_causal_section(payload: dict[str, Any] | None) -> str:
    if not payload:
        return f"{SECTION_TITLE}\n  (unavailable)"
    rz = payload.get("relative_z") or {}
    lines = [
        SECTION_TITLE,
        f"  schema: {payload.get('schema')}",
        f"  status: {payload.get('status')}",
        f"  model: preset={((payload.get('model_authority') or {}).get('public_preset'))} "
        f"line={((payload.get('model_authority') or {}).get('model_line'))}",
        f"  world_dimensionality: {((payload.get('model_authority') or {}).get('world_dimensionality'))}",
        f"  described_as_2d: {payload.get('acanthostega_described_as_2d')}",
        f"  physical_stories: {payload.get('physical_stories_count')}",
        f"  negative_cause_counts: {payload.get('negative_cause_counts')}",
        f"  relative_z: {rz}",
        f"  passive_reachability_trace_present: {payload.get('passive_reachability_trace_present')}",
        f"  held→world trigger: {payload.get('held_to_world_trigger_status')}",
        "  PRESERVES SCIENTIFIC_V3 TickStories · RESEARCHER RECONSTRUCTION ONLY",
        (
            f"  relative_z: control_availability={rz.get('control_availability')} "
            f"authority={rz.get('control_availability_authority')} "
            f"agent_selectable={rz.get('agent_selectable')} "
            f"→ outcome={rz.get('outcome_class')}"
        ),
        (
            f"  z_requests_nonzero={rz.get('z_request_nonzero_count')} "
            f"ebae_refs={rz.get('ebae_event_refs_indexed')} "
            f"aligned_disp={rz.get('aligned_displacement_with_z_request_count')} "
            f"limitations={rz.get('limitations')}"
        ),
    ]
    stories = payload.get("physical_stories") or []
    if stories:
        s0 = stories[0]
        lines.append(
            f"  sample_tick={s0.get('tick')} agent={s0.get('cognitive_agent_id')} cause={s0.get('negative_cause')}"
        )
        ladder = s0.get("causal_ladder") or {}
        for rung in LADDER_RUNGS:
            r = ladder.get(rung) or {}
            lines.append(
                f"    {rung}: {r.get('status')}"
                + (f" ({r.get('observed_cause')})" if r.get("observed_cause") else "")
            )
    return "\n".join(lines)
