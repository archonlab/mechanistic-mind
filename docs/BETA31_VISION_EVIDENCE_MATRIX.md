# BETA31_VISION_EVIDENCE_MATRIX

Analyzer 1.2 forensic classification of Beta 3.1 Scientific V3 fields.

Classes:

- **AGENT_ACCESSIBLE** — present in `ObservationReceipt.accessible`; may enter SMC / PE / PSC as observation.
- **COGNITIVE_INTERNAL** — produced inside cognition; reconstruct from DecisionReceipt compact fields only.
- **SCIENTIFIC_RECEIPT** — recorded on the V3 spine / timeline for reconstruction; not an agent “percept” unless also accessible.
- **RESEARCHER_ONLY** — Observer / WORLD geometry. Must not be treated as agent evidence.
- **NOT_RECORDED** — not stored per tick in V3 CORE.

WORLD remains physically 2D. There is no depth map, z channel, or terrain-geometry vision in agent-accessible state. Distance may affect optical magnitude through the existing sensor pipeline; that is not a depth channel.

| Field | Class | Historical reconstruction |
|---|---|---|
| `exo_0/1/2` | AGENT_ACCESSIBLE | ObservationReceipt when vision ON |
| `surface_c*` | AGENT_ACCESSIBLE | ObservationReceipt when surface discrimination LOW/RICH |
| `spatial_exo_a0…a4` | AGENT_ACCESSIBLE | ObservationReceipt when Spatial Vision ≠ LEGACY |
| `spatial_surface_c*_a*` | AGENT_ACCESSIBLE | ObservationReceipt when Spatial Vision ≠ LEGACY and surface ON |
| `local.FIELD_A/B` | AGENT_ACCESSIBLE | ObservationReceipt + PHYSICAL_SIGNAL_RECEIVED events |
| vestibular `vest_*` | AGENT_ACCESSIBLE | ObservationReceipt |
| neck proprioception `prop_neck_*` | AGENT_ACCESSIBLE | ObservationReceipt |
| selected action / composite motor | COGNITIVE_INTERNAL | DecisionReceipt + MotorReceipt |
| candidate actions / PSC metadata | COGNITIVE_INTERNAL | `candidate_count`, `selection_path`, `selected_candidate_id`; full PSC maps not retained in compact stories |
| predicted consequence / SMC deltas | COGNITIVE_INTERNAL | DecisionReceipt `sensorimotor_consequence` compact (≤12 predictions, ≤48 delta keys) |
| PE / compression internals | COGNITIVE_INTERNAL | **NOT_RECORDED** as per-tick class IDs in V3 CORE DecisionReceipt → `PE_VISUAL_FORENSICS=PARTIAL` |
| prospective composition | COGNITIVE_INTERNAL | `historical_sensorimotor_selection` + `selection_mode`; continuation maps not fully dumped |
| body pose / heading | SCIENTIFIC_RECEIPT | ConsequenceReceipt + timeline `x,y,theta` |
| head heading | SCIENTIFIC_RECEIPT | timeline `head_world_heading` / `head_relative_angle` when recorded |
| other-agent pose | RESEARCHER_ONLY | DERIVED toroidal geometry from timeline; never agent-accessible as pose |
| occlusion provenance / diagnostic sample receipts | RESEARCHER_ONLY | `timeline.vision_optical` / Tiktaalik Eye; do not treat as agent fields |
| terrain / world geometry | RESEARCHER_ONLY | NOT_RECORDED per tick (height maps); seed/config only |
| `body_exposure` / `foreign_body_total` | SCIENTIFIC_RECEIPT | Observer GT; **LEGACY_BODY_VISUAL_EXPOSURE** — not recognition |

## What can be reconstructed historically

- Optical occupancy and quantized diversity of accessible `exo_*`, `surface_c*`, `spatial_*`.
- Consecutive-tick spatial transformations (stable / angular / distribution / magnitude / occlusion-proxy / disocclusion-proxy).
- Action / neck / WAIT coupling as **association**.
- Compact SMC predicted visual deltas when those keys are stored.
- Prospective candidate field lists / support when HSS compact is stored.
- Naturalistic matched pairs on quantized nonvisual accessible fields (residual remains).

## What cannot be reconstructed (do not invent)

- Agent 3D / depth / terrain / color / other-agent recognition.
- Intention, communication, “active vision”, slingshot strategy.
- Exact PE class membership or compressed visual signatures (absent from DecisionReceipt).
- Historical sample-level occlusion provenance (bin-zeroing is a **proxy** → `HISTORICAL_OCCLUSION_RECONSTRUCTION=PARTIAL`).
- Regenerating sensors from current WORLD state.

## Non-interchangeable exposure families

1. `LEGACY_BODY_VISUAL_EXPOSURE` — Observer GT `VISION_EXPOSURE` / `body_exposure` joins.
2. `SURFACE_OPTICAL_EXPOSURE` — occupancy of `surface_c*`.
3. `SPATIAL_OPTICAL_STRUCTURE` — occupancy / diversity of `spatial_exo_*` and `spatial_surface_*`.

Machine-readable copy: Analyzer artifact `BETA31_VISION_EVIDENCE_MATRIX.json`.
