# Acanthostega model line — implementation map

**Status:** Phase 0 seam implemented (canonical preset, not a second UI axis).  
**Public frozen model:** MM 1.0 Tiktaalik Public Beta 3.1.1.  
**Acanthostega Phase 0:** `ACANTHOSTEGA_PHASE0` — same physical/cognitive runtime token as Tiktaalik (`MM_1_0_TIKTAALIK`), distinct `model_line` / identity metadata. Lifecycle biology is not implemented.

Observer has **one** model/preset selector. `model_line` is immutable metadata of the chosen `public_preset`.  
**Scope:** how to add **Acanthostega: Dancing with Death** as a **separate model line** beside frozen Tiktaalik, reusing MM infrastructure.  
**Out of scope:** lifecycle, damage, repair, aging, death, reproduction, genetics, evolution, fitness optimizers, MM rewrite.

Evidence tags: **OBSERVED** (code), **INFERRED** (reasonable from code, not proven), **UNKNOWN** (not established in this recon).

---

### 1. Executive summary

**OBSERVED:** Mechanistic Mind does **not** currently have a first-class registry of interchangeable model lines. Global identity constants in `mechanistic_mind/model/identity.py` are Tiktaalik-only (`MODEL_CODENAME = "Tiktaalik"`, `RUNTIME_VERSION = "MM_1_0_TIKTAALIK"`). Construction of organisms uses `PhysicalSystemConfig` + either `PhysicalSystemRuntime` (one body + world) or `TwoAgentRuntime` (shared `PlanetState`, N slots of `PhysicalSystemRuntime`). Public “model” choice in Observer is **experiment presets** (`TIKTAALIK_BETA31` / `BETA3_RECOMMENDED`), not a model-family switch.

**OBSERVED:** Tiktaalik identity is injected at several layers independently: factory `tiktaalik_config()`, `PhysicalSystemRuntime.model_identity()` → `model.tiktaalik.model_metadata()`, Observer `header_info()` → `display_name()`, snapshot `model` blob, serialize `snapshot_compatibility: "TIKTAALIK"`, `/api/model` → `build_manifest()`.

**INFERRED:** The safest branch is **not** a new physics engine. It is a **registration seam** beside Tiktaalik: a new public_preset + a new identity module, with `PhysicalSystemRuntime.model_identity()` (and Observer header) reading **config-selected** identity while **defaulting** to existing Tiktaalik constants when unset. Shared infrastructure (planet step, body, cognition, motor, V3 receipts, Observer session, Analyzer tick stories) can stay as-is for a first Acanthostega line that is **identity + preset only**.

**OBSERVED mismatch vs naive expectation:** `PROMOTION["two_agent_runtime"] = "NOT_INTEGRATED"` in `identity.py`, but public Beta 3 / 3.1 presets set `agent_count: 2` and `ObserverSession.apply_experiment` constructs `TwoAgentRuntime` when `agent_count >= 2`. The frozen public experiment is two-slot, while canonical Tiktaalik factory/`ObserverSession.reset()` is single-slot `PhysicalSystemRuntime`.

**Recommended branch (minimal):**

```text
MM shared infrastructure
├── Tiktaalik — identity.py + tiktaalik.py + PRESET_BETA31/BETA3 (frozen)
└── Acanthostega — new identity module + new public_preset (does not alias to BETA31)
```

Do not implement organism lifecycle in the first coding pass.

---

### 2. Current model-selection path

```text
launcher / SPA
→ Observer UI “preset” strings
→ apply_experiment payload (public_preset, agent_count, mechanisms, vision, seed)
→ experiment_canonical.normalize_preset_name / merge_canonical / preset_canonical
→ PhysicalSystemConfig (ecology + stamped mechanisms)
→ TwoAgentRuntime  if agent_count ≥ 2
   else PhysicalSystemRuntime
→ world initialize_planet + body initialize_physical_body per slot
→ session step loop + scientific V2/V3 writers
→ Observer frames (serialize) + Analyzer (JSONL / Analyzer Next)
```

| Link | Files / symbols | Notes |
|---|---|---|
| Launch | `launch_psy_observer.bat`, `launch_psy_observer.sh`, `PSYCHOLOGY OBSERVER.sh`, `observer_launcher.py` | **OBSERVED:** launchers start Psy Observer; they do **not** select Tiktaalik vs another model family. |
| UI preset | `web/psy-observer/src/App.tsx` `preset` state; options at ~1983–1985 and ~2591–2593; `buildCompleteApplyPayload` ~2468–2498 | **OBSERVED:** strings `"MM 1.0 — Tiktaalik Beta 3.1"` → `public_preset = 'TIKTAALIK_BETA31'`; Public Beta 3 → `BETA3_RECOMMENDED`. `"MM 1.0 — Tiktaalik"` does **not** set `public_preset` in that branch. `agent_count` comes from `twoAgentExperimental ? 2 : 1`, not from the preset name alone. |
| Header chrome | `web/psy-observer/src/observer/stores.ts` default `modelName: 'Tiktaalik'`; `chrome/ObserverHeader.tsx`; `components/ModelBanner.tsx` | Display fallback is hardcoded Tiktaalik. |
| Canonical preset | `mechanistic_mind/physical_system/experiment_canonical.py` `PRESET_BETA31`, `PRESET_BETA3`, `BETA31_ALIASES`, `BETA3_ALIASES`, `normalize_preset_name`, `preset_canonical`, `canonical_fingerprint`, `merge_canonical` | **OBSERVED:** unknown names: `normalize_preset_name` returns `None`; `preset_canonical` then uses `PRESET_BETA31`. Adding a new name without an explicit branch **collapses to Tiktaalik Beta 3.1**. |
| Session construction | `mechanistic_mind/ui/psy_observer_web/session.py` `ObserverSession.reset` (~449), `apply_experiment` (~6304, agent_count branch ~6435), `get_session` (~6558) | **OBSERVED:** `reset()` always `tiktaalik_config()` + `PhysicalSystemRuntime`. Apply with `agent_count >= 2` → `TwoAgentRuntime`. Process singleton `_SESSION`. |
| Identity | `mechanistic_mind/model/identity.py`; `mechanistic_mind/model/tiktaalik.py` `tiktaalik_config`, `is_canonical_tiktaalik`, `model_metadata`, `build_manifest` | No Acanthostega module. `PhysicalSystemRuntime.__init__(model="tiktaalik")` is the only named constructor switch (`runtime.py` ~155–158). |
| Single-agent runtime | `PhysicalSystemConfig`, `PhysicalSystemRuntime` in `mechanistic_mind/physical_system/runtime.py` | Owns one `world`, one `body`, one `cognition` dict. |
| Two-agent runtime | `mechanistic_mind/physical_system/two_agent.py` `TwoAgentRuntime`, `TECHNICAL_IDS` | Shared world; slots are independent `PhysicalSystemRuntime` instances. |
| World | `initialize_planet` from planet package (called in `PhysicalSystemRuntime.reset`); `step_planet` in `two_agent._step_once` and single-agent `finish_tick` | |
| Organism body | `initialize_physical_body` in `PhysicalSystemRuntime.reset`; `PhysicalBodyConfig` / `PhysicalBodyState` | |
| Cognition / motor | `begin_tick` → `run_cognition_before_action` + `CompositeMotorOutput`; `finish_tick` physics | `runtime.py` `begin_tick` ~579, `finish_tick` ~825, `step` ~1162 |
| Observer API | `mechanistic_mind/ui/psy_observer_web/server.py` FastAPI; `serialize.py` `header_info`, `observer_agent_id` | `/api/model` (~116) calls `session.runtime.model_identity()` and `mechanism_snapshot()` — **INFERRED** 500 on `TwoAgentRuntime` (no `model_identity` / `mechanism_snapshot` on that class). |
| Scientific receipts | `mechanistic_mind/scientific_v3/capture.py` `capture_v3_tick`; `receipts.py` `build_observation_receipt`, `build_decision_receipt`, `build_motor_receipt`, `build_consequence_receipt`; `session.py` `ScientificV3Writer` | Generic `cognitive_agent_id` / `physical_body_id`. |
| Analyzer | `mechanistic_mind/scientific_v3/analyzer_next/tick_stories.py` `TickStory`; `pipeline.py` / `job.py`; research `mechanistic_mind/research/psychology_analyzer/` | Per `cognitive_agent_id`, not hardcoded “exactly two Tiktaalik”. |

---

### 3. Ownership map

| Concern | Current owner | Tiktaalik-specific? | Safe to share? | Required change later |
|---|---|---:|---:|---|
| Process Observer session | `ObserverSession` + `get_session()` singleton | No (generic session) | Yes, **one live runtime per process** | Multi-line simultaneous runs would need a second session or process — not required to *register* a second line |
| Experiment preset | `experiment_canonical.py` | **Yes** (only BETA3/BETA31) | Fingerprint machinery is generic | New preset id that must **not** fall through to BETA31 |
| Model identity constants | `model/identity.py`, `model/tiktaalik.py` | **Yes** | Constants must stay frozen for Tiktaalik | New identity module; dispatch in `model_identity()` |
| Physical config | `PhysicalSystemConfig` | Default `runtime_version=RUNTIME_VERSION` (Tiktaalik) | Yes if defaults unchanged | Optional `runtime_version` / model-line field for Acanthostega |
| Single-body runtime | `PhysicalSystemRuntime` | `model_identity()` always Tiktaalik metadata | Physics/cognition **shareable** | Identity dispatch only |
| Two-slot runtime | `TwoAgentRuntime` | Promotion says NOT_INTEGRATED; public presets use it | Yes as shared multi-body host | Should implement `model_identity()` forwarding (bug today) |
| World / planet | `PlanetState` / `step_planet` | No | Yes | None for registration |
| Body | `PhysicalBodyState` on each slot | Fixed morphology config, no death | Yes | Lifecycle later; **do not** change Tiktaalik body defaults now |
| Cognition | `CognitionConfig` + `empty_cognitive_state` / `run_cognition_before_action` | Canonical vs experimental keys in `tiktaalik.py` | Yes | New line may later differ; first pass can reuse |
| Motor | `CompositeMotorOutput`, PSC resolution on session | Beta 3.1 uses `LOCO_FACTORIZED`; Beta 3 `OBSERVED_COMPOSITE` | Yes | Acanthostega may pick its own PSC mode later |
| Persistence | `PhysicalSystemRuntime.snapshot` schema `mm.physical_system.snapshot.v2`; `TwoAgentRuntime.snapshot` `mm.physical_system.two_agent.snapshot.v1` | Snapshot `model` blob is Tiktaalik metadata; serialize header `snapshot_compatibility: "TIKTAALIK"` | Schemas reusable | New compatibility token **only** for Acanthostega snapshots |
| Scientific V3 | `scientific_v3/` | Generic agent/body ids | Yes | Optional `model_line` in meta later; not required for CORE |
| Observer serialize | `serialize.py` `header_info` | `experiment: display_name()` always Tiktaalik | Mostly | Header must not relabel Tiktaalik runs |
| Analyzer Next | `analyzer_next/tick_stories.py` | No Tiktaalik name in `TickStory` | Yes | Do not assume immortality if later bodies vanish |
| Mechanism registry | `mechanism_registry.py` imports `RUNTIME_VERSION` from identity | Catalog labeled MM 1.0 Tiktaalik | Catalog shareable | Do not retitle catalog as Acanthostega |

---

### 4. Hardcoded assumptions

#### Name “Tiktaalik”

| Claim | Evidence |
|---|---|
| Global identity | **OBSERVED** `identity.py` `MODEL_CODENAME`, `RUNTIME_VERSION`, `display_name()` |
| Factory | **OBSERVED** `tiktaalik.py` `tiktaalik_config()`, `model_metadata()` |
| Runtime | **OBSERVED** `PhysicalSystemRuntime.model_identity` always `from mechanistic_mind.model.tiktaalik import model_metadata` |
| Observer header | **OBSERVED** `serialize.header_info` `experiment: display_name()` even when `model_identity` missing |
| UI | **OBSERVED** `App.tsx` preset options; `InteractPanel.tsx` “SPAWN CONTROLLED TIKTAALIK”; `TiktaalikEye*` components (display name, not a second organism type) |
| `/api/model` | **OBSERVED** `server.model_info` → `build_manifest()` Tiktaalik |
| Gearbox API | **OBSERVED** `server.py` live gearbox payload `"model": "MM_1_0_TIKTAALIK"` (~532) |
| Unknown preset → Beta 3.1 | **OBSERVED** `preset_canonical`: `normalize_preset_name(name) or PRESET_BETA31` |

#### Two persistent agents

| Claim | Evidence |
|---|---|
| Canonical public presets | **OBSERVED** `preset_canonical` sets `"agent_count": 2` for both BETA31 and BETA3 |
| Construction | **OBSERVED** `apply_experiment` `if agent_count >= 2: TwoAgentRuntime(...)` |
| Technical ids | **OBSERVED** `two_agent.TECHNICAL_IDS = ("agent_0", "agent_1")`; extra slots use `f"agent_{i}"` |
| Restore | **OBSERVED** `TwoAgentRuntime.restore` `starts=(tuple(starts[0]), tuple(starts[1]))` — **two start tuples even if more agents were saved** |
| Session reset | **OBSERVED** `reset()` is **one** `PhysicalSystemRuntime`, not two agents |
| Spawn experimenter | **OBSERVED** session can append a third slot (`undercover`) onto `TwoAgentRuntime` (~4871+) |

**INFERRED:** “Always two organisms” is a **public preset / UI default**, not a hard runtime invariant. Slot count is `len(self.slots)`.

#### Immortality / no organism removal

| Claim | Evidence |
|---|---|
| No death/despawn in tick | **OBSERVED** `TwoAgentRuntime._step_once` iterates all slots; no removal |
| IdentityMap | **OBSERVED** `scientific_v3/identity.py` `IdentityMap` comment “Lifecycle registry” but upserts slots; **UNKNOWN** whether Analyzer handles missing bodies mid-run |
| Undercover | **OBSERVED** experimenter slot is additive, not a death mechanic |

**INFERRED:** Organisms persist for the run unless the session rebuilds runtime (Apply/Reset/restore).

#### Fixed body structure

| Claim | Evidence |
|---|---|
| Default body | **OBSERVED** `PhysicalSystemConfig.body` default `default_physical_body2_config`; `preset_canonical` `agent_body` `{mass: 1.0, v_max: 0.4}` |
| Snapshot | **OBSERVED** body config fully serialized in snapshot v2 |
| No morphogenesis | **OBSERVED** deformation/orientation exist as **mechanism flags**, not developmental staging |

#### Save formats

| Claim | Evidence |
|---|---|
| Single-agent | **OBSERVED** `"schema": "mm.physical_system.snapshot.v2"`; `"model": self.model_identity()` |
| Two-agent | **OBSERVED** `"schema": "mm.physical_system.two_agent.snapshot.v1"`, `"experimental": True`, `"promoted": False` — **no top-level `model` identity field** |
| Observer envelope | **OBSERVED** `serialize.py` `"snapshot_compatibility": "TIKTAALIK"` (~460) |
| Restore path | **OBSERVED** `session.py` ~3862 `TwoAgentRuntime.restore(payload)` |

Loading an Acanthostega snapshot as Tiktaalik (or the reverse) is **not guarded** by a model-line check in two-agent restore (**OBSERVED** restore ignores identity).

#### Telemetry / receipts

| Claim | Evidence |
|---|---|
| V3 schemas | **OBSERVED** `mm.scientific_v3.observation.core.v1` etc. in `receipts.py`; ids via `cognitive_agent_id`, `physical_body_id` |
| Capture | **OBSERVED** `capture_v3_tick` iterates `runtime.slots` or single runtime |
| Session meta | **OBSERVED** `_ensure_scientific_locked` records `runtime_type`, `agent_count`, mechanism fingerprint — **not** model codename in the snippet reviewed |
| V2 alongside V3 | **OBSERVED** `ScientificHistoryWriter` + `ScientificV3Writer` |

**INFERRED:** Receipts are model-agnostic; headers/UI are not.

#### Observer

| Claim | Evidence |
|---|---|
| Singleton | **OBSERVED** `_SESSION` / `get_session()` |
| Agent ids | **OBSERVED** `undercover_identity.slot_agent_body_ids` → `agent_{i}` / `body-{i}` / `undercover` |
| `TwoAgentRuntime` has no `model_identity` | **OBSERVED** (no symbol); `header_info` uses `hasattr` |

**INFERRED:** One Observer process cannot host Tiktaalik and Acanthostega **at the same time**. Sequential Apply can replace the runtime.

#### Analyzer

| Claim | Evidence |
|---|---|
| TickStory | **OBSERVED** keyed by `cognitive_agent_id` / `physical_body_id` (`tick_stories.py`) |
| psychology_analyzer | Root `psychology_analyzer.py` + `mechanistic_mind/research/psychology_analyzer/` — **OBSERVED** no `tiktaalik` string in `psychology_analyzer.py` (grep empty) |
| Known limitations | **INFERRED** from prior release notes (HOLD/RETAINED, domain_sources) — not re-audited here |

Analyzer does **not** appear to require the name Tiktaalik. It **does** assume reconstructable per-agent O/D/M/C chains for agents that exist in the JSONL.

---

### 5. Recommended branch seam

```text
MM shared infrastructure
├── Tiktaalik model registration / preset
│     identity.py + tiktaalik.py
│     PRESET_BETA31 / PRESET_BETA3
│     PhysicalSystemRuntime.model_identity → tiktaalik.model_metadata (default)
└── Acanthostega model registration / preset
      new mechanistic_mind/model/acanthostega.py (identity constants only)
      new public_preset id that normalize_preset_name maps explicitly
      apply_experiment constructs the same runtime classes, different identity stamp
```

**Minimal extension points (registration only, no lifecycle):**

1. **`experiment_canonical.py`**  
   Add `PRESET_ACANTHOSTEGA` + aliases. `normalize_preset_name` must return that id, **never** `None` for Acanthostega names (else `preset_canonical` aliases to BETA31). `preset_canonical` branch returns a dict whose `public_preset` is the new id. First implementation may copy Beta 3.1 mechanism flags **or** use a smaller “neutral” map — both are product choices; copying Beta 3.1 **risks scientific confusion** (same organism, different name). Prefer a **distinct** `public_preset` and **distinct** `runtime_version` string even if physics is initially identical.

2. **`PhysicalSystemConfig.runtime_version`**  
   Already exists (`runtime.py` ~97). Tiktaalik factory sets it to `MM_1_0_TIKTAALIK`. Acanthostega Apply should set a **new** token (e.g. `MM_1_0_ACANTHOSTEGA`). Do **not** change the default dataclass value.

3. **`PhysicalSystemRuntime.model_identity`**  
   Dispatch: if `runtime_version` is Tiktaalik (or unset), keep `tiktaalik.model_metadata`. Else call Acanthostega metadata. **Do not** change `tiktaalik.model_metadata` semantics.

4. **`TwoAgentRuntime`**  
   Add `model_identity()` / `mechanism_snapshot()` forwarding to `slots[0]` (or selected slot) so `/api/model` and headers work for the public two-agent path **without** changing Tiktaalik science. This is a **gap in current MM**, not Acanthostega-specific, but touching it must be proven no-op for Tiktaalik frames.

5. **`serialize.header_info`**  
   `experiment` should come from `model_identity().display_name` when present, **falling back** to Tiktaalik `display_name()` only for unlabeled runtimes. Changing fallback behavior is **dangerous**; safer: only override when `runtime_version` is explicitly Acanthostega.

6. **UI**  
   One new `<option>` in `App.tsx` that sets `public_preset` to the new id. Do not rename existing Tiktaalik options. Do not retitle InteractPanel spawn for Tiktaalik.

7. **Save compatibility**  
   Two-agent snapshots should record `model` / `runtime_version`. Restore should **reject** cross-line loads (or load only when token matches). Tiktaalik restore of existing 3.1.1 files must remain accepted.

**Explicitly not a seam (do not “prepare”):** new organism base class, genome type, fitness loop, death flag, generation counter.

**Can Acanthostega start as a named line with a neutral runtime and no lifecycle?**  
**OBSERVED/INFERRED: yes.** Construction is already “config → PhysicalSystemRuntime slots.” Identity is a stamp. Absence of death is the **current** behavior of those classes.

---

### 6. Tiktaalik preservation contract

```text
TIKTAALIK_BETA31_PRESET_CHANGED = NO
TIKTAALIK_SCIENTIFIC_SEMANTICS_CHANGED = NO
TIKTAALIK_REFERENCE_REGRESSION = PASS
```

| Invariant | Meaning | How to check (existing or minimal) |
|---|---|---|
| `TIKTAALIK_BETA31_PRESET_CHANGED = NO` | `preset_canonical(PRESET_BETA31, seed=17)` bytes/fingerprint unchanged; aliases unchanged | **Existing:** `tests/test_cross_tab_experiment_config.py` (`canonical_fingerprint` equality). **Minimal add:** pin `canonical_fingerprint(preset_canonical("TIKTAALIK_BETA31", seed=17))` to a frozen hex (do not change `experiment_canonical` payload). Also pin `beta31_mechanism_map()` key set. |
| `TIKTAALIK_SCIENTIFIC_SEMANTICS_CHANGED = NO` | Cognition defaults, ecology BASELINE, `RUNTIME_VERSION`, snapshot schema, V3 receipt schemas, tick order | **Existing:** `tests/test_tiktaalik_1_0.py` (identity, factory, snapshot identity, negative gates). **Existing:** `tests/test_tiktaalik_baseline_promotion.py`. **Do not** edit `identity.py` / `tiktaalik.py` / `CognitionConfig` defaults / `begin_tick`/`finish_tick`/`_step_once` order. |
| `TIKTAALIK_REFERENCE_REGRESSION = PASS` | Short deterministic runs match prior tests | **Existing:** `test_tiktaalik_1_0.py` bounded-memory / negative tests. Eye/FPV: `test_tiktaalik_eye_phase2.py`, `test_tiktaalik_fpv_phase3.py` (UI/optical; keep green). Cross-tab apply: `test_cross_tab_experiment_config.py`. **Cap:** ≤250 ticks (existing tests already short). |

**Must not change (preservation list):**

- `mechanistic_mind/model/identity.py`
- `mechanistic_mind/model/tiktaalik.py`
- `PRESET_BETA31` / `PRESET_BETA3` payloads and alias sets (except adding **new** aliases that do not steal old names)
- `PhysicalSystemRuntime.begin_tick` / `finish_tick` / `step` (science)
- `TwoAgentRuntime._step_once` order (observation → cognition/motor → `step_planet` → `finish_tick` → contact → signals)
- V3 `receipts.py` schemas for existing CORE fields
- Default `PhysicalSystemConfig` field defaults

**Architectural fact to preserve in docs, not “fix” during Acanthostega work:** `PROMOTION["two_agent_runtime"] = "NOT_INTEGRATED"` while public presets use `TwoAgentRuntime`. Changing promotion class would be a **scientific classification** change for Tiktaalik.

---

### 7. Minimal implementation sequence

Each task: one outcome, short deterministic tests, **no simulation > 250 ticks**, no lifecycle biology.

**Task A — Preset namespace isolation**  
*Result:* `normalize_preset_name("ACANTHOSTEGA…")` ≠ `TIKTAALIK_BETA31`; unknown names still behave as today.  
*Ready when:* unit tests for normalize/preset_canonical; `canonical_fingerprint(TIKTAALIK_BETA31)` unchanged.  
*Tests:* `experiment_canonical` only; no runtime.

**Task B — Identity module + config stamp (no UI)**  
*Result:* `PhysicalSystemConfig.runtime_version` can be Acanthostega token; `PhysicalSystemRuntime.model_identity()` returns Acanthostega metadata **only** when stamped; default/`tiktaalik_config()` unchanged.  
*Ready when:* `test_tiktaalik_1_0.py` still pass; new test `model="tiktaalik"` and unstamped config remain `model_codename == "Tiktaalik"`.  
*Tests:* construct runtime, **0–1 tick**.

**Task C — Apply_experiment registration**  
*Result:* `ObserverSession.apply_experiment({public_preset: ACANTHOSTEGA, agent_count: 1 or 2})` builds runtime with Acanthostega identity; `TIKTAALIK_BETA31` path byte-comparable via fingerprint + `runtime.config.runtime_version == MM_1_0_TIKTAALIK`.  
*Ready when:* two `ObserverSession` instances (not the process singleton) in-process in tests.  
*Tests:* Apply twice, ≤2 ticks each.

**Task D — Observer header / `/api/model` honesty for TwoAgentRuntime**  
*Result:* Tiktaalik two-agent header still shows Tiktaalik; Acanthostega shows Acanthostega; `hasattr` gaps filled **without** changing `display_name()` constants.  
*Ready when:* serialize unit tests on fake/minimal runtimes.  
*Danger:* `header_info` `experiment: display_name()` — only branch on explicit non-Tiktaalik `runtime_version`.

**Task E — Snapshot compatibility token**  
*Result:* Tiktaalik v2 / two_agent.v1 files from 3.1.1 still restore; Acanthostega snapshots carry `runtime_version` and refuse mix-up.  
*Tests:* dump/restore 1 tick; schema string asserts.

**Stop before:** damage, energy-as-life, removal of slots, reproduction, Analyzer taxonomy of “death.”

---

### 8. Risks and unknowns

#### Confirmed risks

- **Preset fall-through:** any unregistered name becomes `TIKTAALIK_BETA31` (`preset_canonical`).  
- **Identity is not architectural isolation:** changing `identity.py` or `model_identity()` default import relabels **all** snapshots and Observer science banners.  
- **Process singleton:** `get_session()` — cannot prove concurrent two-line occupancy in one Observer.  
- **`TwoAgentRuntime.restore` two-start assumption** and missing `model` field — silent mis-restore.  
- **Header always `display_name()` Tiktaalik** — a new line would still look like Tiktaalik until serialize is branched.  
- **Public two-agent vs Reset single-agent** — operators already have two construction paths; a third line increases mis-Apply risk.  
- **`/api/model` + `mechanism_snapshot`** on two-agent public default — existing fragility; easy to “fix” in a way that changes JSON consumed by UI.  
- **Promotion vs practice** for `two_agent_runtime` — documenting Acanthostega on `TwoAgentRuntime` could be misread as promoting that runtime for Tiktaalik.

#### Decisions required

- Should first Acanthostega public_preset use **the same** Beta 3.1 mechanism map (identity-only fork) or a **reduced** map (clearer scientific separation, more UI/test work)?  
- Default `agent_count` for Acanthostega registration (1 vs 2)? Code allows both; public Tiktaalik 3.1 is 2.  
- New snapshot schema vs extra fields on `two_agent.snapshot.v1`? Extra fields are less invasive if restore ignores unknown keys (**UNKNOWN** whether restore is strict).  
- Whether to implement `TwoAgentRuntime.model_identity` in the same change as Acanthostega or as a Tiktaalik-preserving bugfix first.

#### Not confirmed by code

- That Analyzer fails if `agent_count ≠ 2`. **TickStory is per-id.**  
- That a fitness/evolution subsystem exists to hook. **Not found in this recon; do not invent one.**  
- That `IdentityMap` already supports birth/death. Name suggests future lifecycle; **current capture is slot-upsert.**  
- Exact frozen `canonical_fingerprint` hex for Beta 3.1 seed 17 **in-repo** (tests compare equality, do not pin a literal in `test_cross_tab_experiment_config.py`). Pin it in a **new** test when implementing.  
- Packaged 3.1.1 SHA of the tree — release artifact, not a runtime invariant.

---

### 9. Recommended first coding task

**Name:** Register Acanthostega as a **named experiment preset + identity stamp**, with Tiktaalik defaults and Beta 3.1 canonical dict **byte-stable**.

**Scope (do this only):**

1. Add `mechanistic_mind/model/acanthostega.py` with **its own** constants (`MODEL_CODENAME`, `RUNTIME_VERSION`, `display_name`, `model_metadata`). Do **not** import-mutate Tiktaalik constants.  
2. Extend `normalize_preset_name` / `preset_canonical` with an explicit Acanthostega branch.  
3. In `apply_experiment`, after config stamp, if preset is Acanthostega set `cfg.runtime_version` to the Acanthostega token.  
4. In `PhysicalSystemRuntime.model_identity`, dispatch on `cfg.runtime_version` (Tiktaalik default path **literally** remains `tiktaalik.model_metadata`).  
5. Tests: fingerprint + `test_tiktaalik_1_0.py` + new identity dispatch tests (0–2 ticks).

**Files expected to change:**

- `mechanistic_mind/model/acanthostega.py` (new)  
- `mechanistic_mind/physical_system/experiment_canonical.py`  
- `mechanistic_mind/ui/psy_observer_web/session.py` (`apply_experiment` stamp only)  
- `mechanistic_mind/physical_system/runtime.py` (`model_identity` dispatch only)  
- `tests/` new file + maybe one assert in cross-tab tests  

**Optional tiny UI (same task or next):** one `App.tsx` `<option>` — not required to prove the seam.

**Files that must not change in this task:**

- `mechanistic_mind/model/identity.py`  
- `mechanistic_mind/model/tiktaalik.py`  
- `PhysicalSystemRuntime.begin_tick` / `finish_tick` / `step`  
- `TwoAgentRuntime._step_once`  
- `scientific_v3/receipts.py` field semantics  
- `PRESET_BETA31` / `BETA31_EXPERIMENTAL_ON` contents  
- Ecology / body default factories  
- Analyzer pipelines  
- Launchers  

**Acceptance criteria:**

- `preset_canonical("TIKTAALIK_BETA31", seed=17)` fingerprint **identical** to pre-change.  
- `PhysicalSystemRuntime(model="tiktaalik")` and `tiktaalik_config()` metadata **identical**.  
- `pytest tests/test_tiktaalik_1_0.py tests/test_tiktaalik_baseline_promotion.py tests/test_cross_tab_experiment_config.py` pass.  
- New tests: Acanthostega preset id does not normalize to `TIKTAALIK_BETA31`; stamped runtime `model_codename` is Acanthostega; unstamped is Tiktaalik.  
- No lifecycle fields. No new tick order. No sim > 2 ticks in new tests.

**Test plan:**

```text
pytest tests/test_tiktaalik_1_0.py \
       tests/test_tiktaalik_baseline_promotion.py \
       tests/test_cross_tab_experiment_config.py \
       tests/test_acanthostega_model_line_registration.py
```

(The last file does not exist yet.) Include `canonical_fingerprint` pin for Beta 3.1 seed 17 captured **before** edits.

**Proof Tiktaalik did not change:**

1. Frozen fingerprint of `preset_canonical(PRESET_BETA31, seed=17)`.  
2. Unchanged `identity.py` / `tiktaalik.py` (git diff empty).  
3. `test_tiktaalik_1_0.py` identity + snapshot `model_codename == "Tiktaalik"`.  
4. Apply `TIKTAALIK_BETA31` in a unit `ObserverSession()` → `runtime.config.runtime_version == "MM_1_0_TIKTAALIK"` and `model_identity()["model_codename"] == "Tiktaalik"` when `model_identity` exists.

---

*End of recon. Implementation starts only on a separate request.*
