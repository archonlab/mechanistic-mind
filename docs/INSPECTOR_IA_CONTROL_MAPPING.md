# Inspector IA — old control → new location

UI/navigation only. Runtime/science endpoints unchanged.

## LEVEL-1 (left MM Control rail)

| Old left destination | New Inspector section | Workspace |
|---|---|---|
| Experiment (COLD nested device-body) | EXPERIMENT (full right Inspector) | INSPECT |
| Intervention / Experimenter | INTERVENTION | INSPECT |
| Observe | OBSERVE | INSPECT |
| Sensors | SENSORS | INSPECT |
| Signals | SIGNALS | INSPECT |
| Analyze Results | Analyze workspace (unchanged) | ANALYZE |
| Runs | RUNS | INSPECT |
| World Status | WORLD_STATUS | INSPECT |

Rail clicks collapse the launcher and switch the **entire** right Inspector. Expanded left dock is launcher tiles only.

## Experiment

| Old COLD screen / control | New tab | Group | Backend | Mutability |
|---|---|---|---|---|
| Set Ecology presets | Ecology | Ecology preset | `POST /api` live intervention category=ecology | LIVE |
| Climate / R_A / R_B gates | Ecology | Climate / R_A / R_B | `POST /api/mechanisms/:id` | LIVE if ablatable |
| APPLY LIVE (ecology) | Ecology | Apply | live intervention | LIVE |
| Vision / illumination mechs | Perception | Vision | `POST /api/mechanisms/:id` | LIVE |
| ACTIVE_SENSOR_ORIENTATION | Perception | Status | frame `physical.orientation` | STATUS / GT |
| Set Resources R_A/R_B metrics | Body | Resources GT | frame `effective_world` | GT display |
| Set Model cognition / Hz / history | Cognition + Model | Model | live intervention category=model | LIVE (cognition/Hz); two-agent / mass / vmax PRE-RUN (world reset) |
| APPLY LIVE (model) | Cognition / Model | Apply | live intervention | LIVE |
| Predictive / PSC / CPO / CGP / PPC / SMC / HSS | Predictive | PSC | `POST /api/mechanisms/:id`, PSC mode API | LIVE if ablatable; motor resolution is MODE not ON/OFF |
| Other ablatable list | Ablations | Mechanisms | `POST /api/mechanisms/:id` | LIVE if ablatable |
| Flow channel ablations | Ablations | Unavailable | none | NOT INDEPENDENTLY ABLATABLE |
| Set World seed/size + APPLY & RESET | World | World-structural | apply experiment / reset | PRE-RUN (rebuild generation) |
| Effective World / Interventions / Mechanisms floats | World / Ablations | Opens floating window | existing float APIs | Observer |

## Sensors

| Old | New tab | Backend | Mutability |
|---|---|---|---|
| VisionExperimenterControl ON + R1/R2/R3 | Vision | `/api/mechanisms/physical_near_field_vision`, `/api/vision/radius` | LIVE (wired; radius disabled only if Vision OFF) |
| NearFieldSensorPanel | Vision | same | LIVE toggles; GT metrics |
| VisionBars exo_* | Vision extras | agent_observation | AGENT |
| VestibularProprioceptionPanel | Vestibular / Proprioception | mechanisms + frame | LIVE toggles where wired; GT otherwise |
| Body x,y,vx, action, R_A/R_B | Body | frame physical | GT |
| Illumination cycle / illumination | Ambient | mechanisms + frame | LIVE flag + GT value |
| Open Vision Inspector | Vision | float `sensor_inspector` | Observer |

## Intervention (controlled Tiktaalik)

| Old cramped card | New tab / accordion | Backend | Mutability |
|---|---|---|---|
| Spawn / near 0 / near 1 / Remove | Controlled Agent → Spawn | experimenter spawn/remove | INTERVENTION (disabled with reason if already spawned) |
| Ordinary / Research mobility | Spawn | `experimenterSetMobility` | INTERVENTION when CONTROL_ACTIVE |
| N/S/W/E / WAIT | Movement | `experimenterCommand` ACTION | INTERVENTION; disabled + reason if not spawned |
| FIELD_A / FIELD_B / specimen replay | Fields | command + signal library | INTERVENTION when active |
| Target / Capture / Test | Interaction | setTarget, capture, testCapture | INTERVENTION; capture/test not spawn-gated |
| Camera FREE / FOLLOW YOU / TARGET | Camera | `cameraFollowStore` → WorldMap `followXY` | Observer-only view |

## Observe / Signals / Runs / World Status

| Old | New | Notes |
|---|---|---|
| ObserveV2 + overlay/inspector/geometry/agent/signal floats | OBSERVE all tabs; cognition/body/predictive extra panels | extras always mounted; tab adds inspectors |
| MechanismAwareSignals + Oscillatory + SMC | SIGNALS tabs | physical coupling ≠ communication |
| Run catalog + overview | RUNS | existing archive |
| Effective world fingerprint / overrides | WORLD_STATUS | GT |

## Dead / inert controls found

| Symptom | Cause | Fix |
|---|---|---|
| Vision R= buttons looked dead while RUN | InspectorDock omitted `onSetVisionRadius` / toggle handlers | Wired through InspectWorkspace |
| Duplicate `title=` on radius buttons overwrote LIVE tooltip | Second title attribute | Single LIVE/OFF/unwired title |
| Experimenter lower buttons no-op / unreachable | Nested `.panel{overflow:auto}` + COLD device-body + maxHeight 160 lists clipping hits | Full Inspector + overflow visible + accordions; disable+title when not CONTROL_ACTIVE |
| Camera follow did nothing | Local unused state, never panned WorldMap | `cameraFollowStore` → WorldPane `followXY` |
| Flow channel switches | Not independently ablatable | Explicit UNAVAILABLE copy, no fake toggle |
