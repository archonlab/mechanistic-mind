#!/usr/bin/env python3
"""Validate documentation structure without executing Mechanistic Mind."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
K = ROOT / "knowledge"
S = K / "structured"

def main():
    errors = []
    data = {}
    for p in S.glob("*.json"):
        try: data[p.name] = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc: errors.append(f"invalid JSON {p}: {exc}")
    exps = data.get("experiments.json", [])
    ids = [e.get("experiment_id") for e in exps]
    if len(ids) != len(set(ids)): errors.append("duplicate experiment IDs")
    for e in exps:
        if not e.get("provenance"): errors.append(f"missing provenance: {e.get('experiment_id')}")
        doc = K / "experiments" / (e["experiment_id"].lower().replace(".", "_") + ".md")
        if not doc.exists(): errors.append(f"missing experiment document: {doc}")
        for p in e.get("provenance", []):
            if not (ROOT / p).exists(): errors.append(f"broken provenance path: {p}")
    claim_ids = [c.get("claim_id") for c in data.get("claims.json", [])]
    if len(claim_ids) != len(set(claim_ids)): errors.append("duplicate claim IDs")
    edge_ids = [e.get("edge_id") for e in data.get("causal_edges.json", [])]
    if len(edge_ids) != len(set(edge_ids)): errors.append("duplicate edge IDs")
    runtime_refs = []
    for p in (ROOT / "mechanistic_mind").rglob("*.py"):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if "knowledge/" in txt or "knowledge\\" in txt: runtime_refs.append(str(p.relative_to(ROOT)))
    if runtime_refs: errors.append("runtime references knowledge/: " + ", ".join(runtime_refs))
    timeline_path = K / "timeline.md"
    if not timeline_path.exists():
        errors.append("missing timeline.md")
        timeline = ""
    else:
        timeline = timeline_path.read_text(encoding="utf-8")
    for eid in ids:
        if eid not in timeline: errors.append(f"timeline missing {eid}")
    if errors:
        print("VALIDATION FAILED")
        print("\n".join("- " + x for x in errors))
        raise SystemExit(1)
    print(f"VALIDATION PASSED: {len(ids)} experiments, {len(claim_ids)} claims, {len(edge_ids)} causal edges; runtime isolation confirmed")

if __name__ == "__main__": main()
