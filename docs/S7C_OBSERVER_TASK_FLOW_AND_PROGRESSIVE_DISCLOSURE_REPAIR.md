# S7C — Observer Task Flow and Progressive Disclosure Repair

**Status:** Phase A (nav + Apply safety) complete · **Phase B (FPV center + disclosure + popovers) complete**  
**Does not start Beta 4.1.** No physics / cognition / S6 mutation.

## Corrected default authority (do not regress)

| Key | Value |
|-----|-------|
| PROSPECTIVE_SCENARIO_COMPETITION_DEFAULT | OFF |
| EXPERIMENTAL_PHYSICAL_SIGNAL_DEFAULT | ON |
| CANONICAL_DEFAULT_OFF_COUNT | **1** |
| R3_FORCED_CANONICAL | NO |
| OCCLUSION_FORCED_CANONICAL | NO |

Obsolete assumption of “exactly two default-OFF mechanisms” is **not** server truth.

## Phase B contracts

- `PRIMARY_PHENOMENON_FIRST` — selected observation owns the center
- `FPV_IN_NARROW_SIDEBAR = NO` — FPV Vision closes left dock; `FpvObservationWorkspace` uses exact O4 panel
- Progressive disclosure via `PhenomenonDetails` (`<details>`)
- Setting help via accessible `SettingInfoHelp` (ⓘ)
- Single global Apply on Experiment → Review / Apply

## Artifacts

`results/s7c_observer_task_flow_and_progressive_disclosure_repair/`

## Next safe seam

S7C polish / remaining destination depth · **not** Beta 4.1.
