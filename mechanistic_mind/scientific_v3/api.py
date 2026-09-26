"""Normalized SCIENTIFIC_V3 CORE evidence API (read-only).

Default load is an offset index plus on-demand line reads. It must not
materialize every DecisionReceipt into RAM (aged runs store ~GB of JSONL).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.is_file():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def _compact_observation(r: dict[str, Any]) -> dict[str, Any]:
    acc = r.get("accessible") or {}
    prefixes = (
        "local.FIELD_", "exo_", "surface_c", "spatial_",
        "body.", "internal.", "vest_", "prop_neck_", "osc_",
    )
    acc_c = {k: v for k, v in acc.items() if any(str(k).startswith(p) for p in prefixes)}
    return {
        "tick": r.get("tick"),
        "cognitive_agent_id": r.get("cognitive_agent_id"),
        "physical_body_id": r.get("physical_body_id"),
        "observation_id": r.get("observation_id"),
        "provenance": r.get("provenance"),
        "accessible": acc_c,
    }


def _compact_decision(r: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "tick", "cognitive_agent_id", "physical_body_id",
        "selection_path", "selection_source", "selection_mode", "selection_rule",
        "selected_action_legacy", "selected_candidate_id", "candidate_count",
        "fallback_reason", "observation_id", "decision_id", "motor_id",
    )
    return {k: r.get(k) for k in keys}


def _compact_motor(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "tick": r.get("tick"),
        "cognitive_agent_id": r.get("cognitive_agent_id"),
        "physical_body_id": r.get("physical_body_id"),
        "motor_schema": r.get("motor_schema"),
        "components": r.get("components"),
        "legacy_token": r.get("legacy_token"),
        "legacy_token_provenance": r.get("legacy_token_provenance"),
        "decision_id": r.get("decision_id"),
        "motor_id": r.get("motor_id"),
    }


def _compact_consequence(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "physical_body_id": r.get("physical_body_id"),
        "tick_from": r.get("tick_from"),
        "tick_to": r.get("tick_to"),
        "pose_delta": r.get("pose_delta"),
        "orientation_delta": r.get("orientation_delta"),
        "resource_delta": r.get("resource_delta"),
        "attribution": r.get("attribution"),
        "motor_id": r.get("motor_id"),
        "consequence_id": r.get("consequence_id"),
    }


def _scan_compact(path: Path, key_fn, compact_fn) -> tuple[dict[Any, int], dict[Any, dict[str, Any]]]:
    idx: dict[Any, int] = {}
    compact: dict[Any, dict[str, Any]] = {}
    if not path.is_file():
        return idx, compact
    with path.open("rb") as f:
        while True:
            pos = f.tell()
            raw = f.readline()
            if not raw:
                break
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            key = key_fn(obj)
            if key is None:
                continue
            idx[key] = pos
            compact[key] = compact_fn(obj)
    return idx, compact


class RunEvidence:
    """Read a V3 CORE package without retaining all receipts in memory."""

    def __init__(self, directory: str | Path, *, materialize: bool = False) -> None:
        self.directory = Path(directory)
        self.meta = self._load_json(self.directory / "scientific_v3_meta.json")
        self.identity_map = self._load_json(self.directory / "identity_map.json")
        self._materialize = bool(materialize)
        self._obs_path = self.directory / "scientific_observations.jsonl"
        self._dec_path = self.directory / "scientific_decisions.jsonl"
        self._motor_path = self.directory / "scientific_motors.jsonl"
        self._cons_path = self.directory / "scientific_consequences.jsonl"
        self._spine_path = self.directory / "scientific_spine.jsonl"
        self._fh: dict[Path, Any] = {}
        if self._materialize:
            self._obs = {
                (r.get("cognitive_agent_id"), int(r["tick"])): r
                for r in _iter_jsonl(self._obs_path)
                if "tick" in r
            }
            self._dec = {
                (r.get("cognitive_agent_id"), int(r["tick"])): r
                for r in _iter_jsonl(self._dec_path)
                if "tick" in r
            }
            self._motor = {
                (r.get("cognitive_agent_id"), int(r["tick"])): r
                for r in _iter_jsonl(self._motor_path)
                if "tick" in r
            }
            self._cons = {
                (r.get("physical_body_id"), int(r["tick_from"])): r
                for r in _iter_jsonl(self._cons_path)
                if "tick_from" in r
            }
            self._spine = list(_iter_jsonl(self._spine_path))
            self._obs_idx = self._dec_idx = self._motor_idx = self._cons_idx = None
        else:
            self._spine = None
            self._obs_idx, self._obs = _scan_compact(
                self._obs_path,
                lambda r: (r.get("cognitive_agent_id"), int(r["tick"])) if "tick" in r else None,
                _compact_observation,
            )
            self._dec_idx, self._dec = _scan_compact(
                self._dec_path,
                lambda r: (r.get("cognitive_agent_id"), int(r["tick"])) if "tick" in r else None,
                _compact_decision,
            )
            self._motor_idx, self._motor = _scan_compact(
                self._motor_path,
                lambda r: (r.get("cognitive_agent_id"), int(r["tick"])) if "tick" in r else None,
                _compact_motor,
            )
            self._cons_idx, self._cons = _scan_compact(
                self._cons_path,
                lambda r: (r.get("physical_body_id"), int(r["tick_from"])) if "tick_from" in r else None,
                _compact_consequence,
            )

    def close(self) -> None:
        for fh in self._fh.values():
            try:
                fh.close()
            except Exception:
                pass
        self._fh.clear()

    def __enter__(self) -> "RunEvidence":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}

    def _read_at(self, path: Path, pos: int) -> dict[str, Any] | None:
        fh = self._fh.get(path)
        if fh is None:
            if not path.is_file():
                return None
            fh = path.open("rb")
            self._fh[path] = fh
        fh.seek(pos)
        raw = fh.readline()
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return obj if isinstance(obj, dict) else None

    def iter_spine(self) -> Iterator[dict[str, Any]]:
        if self._spine is not None:
            yield from self._spine
            return
        yield from _iter_jsonl(self._spine_path)

    def spine_max_tick(self) -> int | None:
        mx = None
        for s in self.iter_spine():
            try:
                t = int(s["tick"])
            except (KeyError, TypeError, ValueError):
                continue
            mx = t if mx is None else max(mx, t)
        return mx

    @property
    def schema_version(self) -> str | None:
        return self.meta.get("schema")

    @property
    def evidence_tier(self) -> str | None:
        return self.meta.get("evidence_tier")

    @property
    def coverage(self) -> dict[str, Any]:
        return self.meta.get("coverage") or {}

    def get_observation(self, agent_id: str, tick: int) -> dict[str, Any] | None:
        key = (agent_id, int(tick))
        if self._obs is not None:
            return self._obs.get(key)
        pos = (self._obs_idx or {}).get(key)
        return self._read_at(self._obs_path, pos) if pos is not None else None

    def get_decision(self, agent_id: str, tick: int) -> dict[str, Any] | None:
        key = (agent_id, int(tick))
        if self._dec is not None:
            return self._dec.get(key)
        pos = (self._dec_idx or {}).get(key)
        return self._read_at(self._dec_path, pos) if pos is not None else None

    def get_motor(self, agent_id: str, tick: int) -> dict[str, Any] | None:
        key = (agent_id, int(tick))
        if self._motor is not None:
            return self._motor.get(key)
        pos = (self._motor_idx or {}).get(key)
        return self._read_at(self._motor_path, pos) if pos is not None else None

    def get_consequence(self, body_id: str, tick: int) -> dict[str, Any] | None:
        key = (body_id, int(tick))
        if self._cons is not None:
            return self._cons.get(key)
        pos = (self._cons_idx or {}).get(key)
        return self._read_at(self._cons_path, pos) if pos is not None else None

    def has_observation(self, agent_id: str, tick: int) -> bool:
        key = (agent_id, int(tick))
        if self._obs is not None:
            return key in self._obs
        return key in (self._obs_idx or {})

    def has_decision(self, agent_id: str, tick: int) -> bool:
        key = (agent_id, int(tick))
        if self._dec is not None:
            return key in self._dec
        return key in (self._dec_idx or {})

    def has_motor(self, agent_id: str, tick: int) -> bool:
        key = (agent_id, int(tick))
        if self._motor is not None:
            return key in self._motor
        return key in (self._motor_idx or {})

    def has_consequence(self, body_id: str, tick: int) -> bool:
        key = (body_id, int(tick))
        if self._cons is not None:
            return key in self._cons
        return key in (self._cons_idx or {})

    def trace_chain(self, agent_id: str, tick: int) -> dict[str, Any]:
        obs = self.get_observation(agent_id, tick)
        dec = self.get_decision(agent_id, tick)
        mot = self.get_motor(agent_id, tick)
        body_id = None
        if dec:
            body_id = dec.get("physical_body_id")
        elif obs:
            body_id = obs.get("physical_body_id")
        cons = self.get_consequence(body_id, tick) if body_id else None
        complete = all(x is not None for x in (obs, dec, mot, cons))
        broken = []
        if obs is None:
            broken.append("missing_observation")
        if dec is None:
            broken.append("missing_decision")
        elif obs and dec.get("observation_id") != obs.get("observation_id"):
            broken.append("decision_observation_mismatch")
        if mot is None:
            broken.append("missing_motor")
        elif dec and mot.get("decision_id") != dec.get("decision_id"):
            broken.append("motor_decision_mismatch")
        if cons is None:
            broken.append("missing_consequence")
        elif mot and cons.get("motor_id") != mot.get("motor_id"):
            broken.append("consequence_motor_mismatch")
        return {
            "tick": int(tick),
            "cognitive_agent_id": agent_id,
            "complete": complete and not broken,
            "broken_reasons": broken,
            "observation": obs,
            "decision": dec,
            "motor": mot,
            "consequence": cons,
        }

    def reconstruction_summary(self) -> dict[str, Any]:
        expected = 0
        complete = 0
        broken_counts: dict[str, int] = {}
        for s in self.iter_spine():
            if not s.get("decision_id"):
                continue
            expected += 1
            agent = str(s.get("cognitive_agent_id") or "")
            try:
                tick = int(s["tick"])
            except (KeyError, TypeError, ValueError):
                continue
            body = s.get("physical_body_id")
            missing: list[str] = []
            if not self.has_observation(agent, tick):
                missing.append("missing_observation")
            if not self.has_decision(agent, tick):
                missing.append("missing_decision")
            if not self.has_motor(agent, tick):
                missing.append("missing_motor")
            if not body or not self.has_consequence(str(body), tick):
                missing.append("missing_consequence")
            if missing:
                for r in missing:
                    broken_counts[r] = broken_counts.get(r, 0) + 1
            else:
                complete += 1
        n_obs = len(self._obs) if self._obs is not None else len(self._obs_idx or {})
        n_dec = len(self._dec) if self._dec is not None else len(self._dec_idx or {})
        n_mot = len(self._motor) if self._motor is not None else len(self._motor_idx or {})
        n_cons = len(self._cons) if self._cons is not None else len(self._cons_idx or {})
        return {
            "schema_version": self.schema_version,
            "evidence_tier": self.evidence_tier,
            "identity_bodies": len((self.identity_map or {}).get("bodies") or []),
            "coverage": self.coverage,
            "ticks_expected_autonomous": expected,
            "observation_receipts": n_obs,
            "decision_receipts": n_dec,
            "motor_receipts": n_mot,
            "consequence_receipts": n_cons,
            "complete_odmc_chains": complete,
            "complete_odmc_over_expected": f"{complete} / {expected}",
            "broken_chains_by_reason": broken_counts,
            "health": (self.meta or {}).get("health"),
        }

    @staticmethod
    def detect_evidence_version(directory: str | Path) -> str:
        d = Path(directory)
        if (d / "scientific_v3_meta.json").is_file() or (d / "scientific_spine.jsonl").is_file():
            return "SCIENTIFIC_V3"
        if (d / "scientific_meta.json").is_file() or (d / "scientific_timeline.jsonl").is_file():
            try:
                meta = json.loads((d / "scientific_meta.json").read_text()) if (d / "scientific_meta.json").is_file() else {}
            except Exception:
                meta = {}
            mode = str(meta.get("telemetry_mode") or "")
            if "V2" in mode or mode.endswith("V2_TIERED"):
                return "SCIENTIFIC_V2_TIERED"
            return "SCIENTIFIC_V1_OR_V2"
        return "NOT_RECORDED"
