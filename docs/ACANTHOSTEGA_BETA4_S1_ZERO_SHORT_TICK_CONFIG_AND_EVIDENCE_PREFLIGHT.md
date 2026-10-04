# ACANTHOSTEGA_BETA4_S1_ZERO_SHORT_TICK_CONFIG_AND_EVIDENCE_PREFLIGHT

**Seam:** S1 preflight only.  
**Public model:** `ACANTHOSTEGA_BETA4` (unchanged).  
**Expected RC fingerprint (P7):** `e658e1ef405d95388a2a7322196fb93678ec803c73e07ff59ec199b4658075ac`  
**Simulated ticks this seam:** ≤40 budget; actual probes used **5**.  
**No pilot/primary. No live Observer mutation. No production physics/cognition/protocol rewrite.**

Artifacts: `results/acanthostega_beta4_s1_zero_short_tick_config_and_evidence_preflight/`

---

## 1. Freshness and fingerprint

- Branch `main`; HEAD matches P7 (`5d0f14cd…`).
- Canonical fingerprint and `web_dist` asset unchanged.
- **Dirty-tree fingerprint changed** (P7: 518 files / `f0e26c2c…` → current: more dirty files after architecture docs).  
  Therefore `RELEASE_CANDIDATE_FINGERPRINT_MATCH = false`.  
  Changed input: **`dirty_state_fingerprint` only**. Expected fingerprint was **not** rewritten.

## 2. Authoritative recovery

Recovered from:
- `docs/ACANTHOSTEGA_BETA4_SCIENTIFIC_BEHAVIORAL_VALIDATION_ARCHITECTURE.md`
- `results/beta4_scientific_behavioral_validation_architecture/*`
- P7 `DEBT_REGISTER.md` / RC manifest

Nine conditions C0–C8 recovered **verbatim** from `EXPERIMENTAL_CONDITIONS.md`.

## 3. Condition matrix completeness — BLOCKER

| ID | Unique? | Issue |
|----|---------|-------|
| C0 | yes | shipped baseline |
| C1 | yes | LEGACY_FIRST throughout |
| C2 | yes* | schedule defined, but stock auto-enable incomplete (see §5) |
| C3 | yes | config-equivalent twin of C1 |
| **C4** | **no** | PSC “As C2 or C1 per contrast” |
| C5 | yes† | optical control as C1 segment (†agent count listed 1–2) |
| C6 | yes | acoustic source OFF as C1 |
| **C7** | **no** | PSC “As C1/C2” |
| **C8** | **no** | capability probe APIs/set not enumerated |

**Primary verdict: `C. S1_BLOCKED_CONDITION_MATRIX_INCOMPLETE`.**  
S1 does **not** invent missing definitions.

## 4. Config digests

For uniquely defined conditions, causal digests are deterministic:
- rebuild-stable;
- C0 ≠ C1;
- seed-sensitive;
- C1 ≡ C3 at same seed (twin pairing excluded from causal digest).

Ambiguous conditions produce `status=AMBIGUOUS` with `digest=null`.

## 5. PSC schedule / off-twin

Short probe (threshold=1, not 1000; 2+2+1 ticks):
- Scheduled path **does** enable `SCENARIO_COMPETITION` at threshold via `psc_off_ticks`.
- **Does not** open `sensorimotor_consequence_withhold_from_psc` (remains True) — architecture C2 requires withhold open at enable.
- PSC-OFF twin **never** auto-enables.
- Manual intervention is **not** part of scientific protocol.
- **Restore drops `psc_off_ticks`** (field is setattr-only, not on `CognitionConfig` dataclass) → schedule not preserved across restore.

These are additional **E-class** blockers recorded after the primary C blocker.

## 6. Causal ablations (representable)

| Control | Ready? | Mechanism |
|---------|--------|-----------|
| Vision | yes | `source.enabled=False` and/or O3 capability off |
| Hearing | yes | `osc.emission_enabled=False` |
| Signaling RX | yes | `osc.perception_enabled=False` |
| Effector Z | yes | `manipulator_relative_world_actuation.enabled=False` (EBAE can remain on) |
| PSC | **no** | withhold-open + restore preservation gaps |

## 7. Evidence / Analyzer

FULL_SCIENTIFIC authorities cover identities, motors, observations, consequences, OSC/O4/O5 paths.  
Partial: opportunity-normalized terrain ladder (needs joins); PSC withhold-open receipt.  
Analyzer can compute most preregistered metrics from saved evidence without replaying physics; seed is replication unit; ticks not i.i.d.; TRUE_ZERO/MISSING/INVALID/FAIL/INCONCLUSIVE_UNDERPOWERED remain distinct. FPV is not numeric authority.

## 8. Isolation / privacy

No live-run mutation; no researcher metadata→cognition; no FPV numeric authority; digests must key caches; ablation metadata not agent input.

## 9. Verdict and next seam

**`C. S1_BLOCKED_CONDITION_MATRIX_INCOMPLETE`**

**Do not start S2.**  
**Next safe seam:** uniquely fix C4/C7/C8 PSC attachments and C8 probe enumeration in the preregistration artifacts (documentation-only if possible), then also resolve C2 withhold-open receipt + `psc_off_ticks` restore preservation **without** changing public-model physics — then re-run S1.
