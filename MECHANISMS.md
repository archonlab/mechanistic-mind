# MECHANISMS

Concise public reference for Mechanistic Mind 2.0 — Tiktaalik: Undercover — Public Beta 1.

Internal schema / protocol versions (e.g. snapshot schema, Observer API `0.2.0`) are independent of the product version **2.0** and are not rewritten for branding.

---

## Cognition / PSC

| | |
|--|--|
| **Purpose** | Bounded predictive structures, prospective composition, scenario competition → action selection |
| **Inputs** | Agent observation (including anonymous exo), internal predictive stores |
| **Outputs** | Selected action / selection metadata |
| **Bounded state** | Causal trace capacity and store limits apply |
| **Observer** | Selection, traces, metrics visible |
| **Cognition access** | This *is* the cognitive path |
| **Limitation** | Computationally expensive; not “understanding” |

## Body / orientation / deformation / work

| | |
|--|--|
| **Purpose** | Physical body dynamics, orientation, deformation, mechanical work reservoir |
| **Inputs** | Motor commands, contacts, resource conversion, world forces |
| **Outputs** | Pose, rates, work ledger |
| **Observer** | Body panels, motion receipts |
| **Limitation** | Abstract mechanical work ≠ metabolism / emotion |

## Resources A/B + complementary conversion

| | |
|--|--|
| **Purpose** | Independent environmental stocks; conversion to mechanical work |
| **Inputs** | World A/B fields, transfer rules |
| **Outputs** | Body-local stocks, work credit |
| **Observer** | Resource overlays / ledgers |
| **Limitation** | Not food/hunger metaphors |

## Terrain / ambient world / climate ecology

| | |
|--|--|
| **Purpose** | Structured terrain and optional spatiotemporal climate ecology |
| **Default** | Follows frozen public experiment defaults (not retuned for packaging) |
| **Observer** | World map layers |
| **Limitation** | Climate ecology is a mechanism switch; performance audits sometimes disable it for measurement only |

## Physical signals / contact

| | |
|--|--|
| **Purpose** | Field coupling and contact events between bodies/world |
| **Observer** | Signal / contact inspectors |
| **Cognition** | Via observation channels only |
| **Limitation** | Not demonstrated communication |

## Near-field vision (physical)

| | |
|--|--|
| **Purpose** | Local optical exteroception |
| **Inputs** | Moore candidates at radius R, FOV, illumination, body optics |
| **Outputs** | Anonymous `exo_0`, `exo_1`, `exo_2` |
| **Radius** | R=1 → max 8 candidates; R=2 → 24; R=3 → 48 |
| **Default** | **R=1** |
| **Observer** | Sensor Inspector, FOV overlay; LIVE R control with provenance |
| **Cognition** | Exo channels only — **no identity** |
| **Limitation** | Candidates ≠ guaranteed visibility; no LOOK/gaze act; no R=4 |

## Visual Forensics

| | |
|--|--|
| **Purpose** | Scientific evidence of foreign-body optical exposure |
| **Path** | Same authoritative vision path as Sensor Inspector |
| **Body-derived delta** | final exo − exo without foreign bodies (actual composition semantics) |
| **Threshold** | `foreign_body_total > 1e-12` |
| **Storage** | Compact `vision_optical` on scientific timeline (~O(1) append) |
| **Analyzer** | Episodes / coverage on demand — not rebuilt every Play tick |
| **Limitation** | Exposure ≠ recognition; cognition linkage often NOT_ESTABLISHED |

## Undercover

See `UNDERCOVER.md`. Exactly one physical Undercover body; controller nonphysical.

## Two-agent runtime

Shared world, two cognitive Tiktaalik bodies (plus optional Undercover body).
