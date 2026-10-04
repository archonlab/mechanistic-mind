# OSC_EMISSION_EXPRESSIVITY_AND_RECEIVER_DISCRIMINABILITY_AUDIT

**Status:** observational audit only — no mechanics changed.  
**Scope:** Acanthostega endogenous `OSC_EMIT` path under Local Physical Signal Transport (LPS).  
**Not in scope:** language, meaning, communication claims, contact/impact acoustics as controllable repertoire, researcher free-band interventions except as contrast.

---

## 0. Three spaces (do not conflate)

| Space | Definition | Agent control |
|-------|------------|---------------|
| **S_motor** — motor-selectable repertoire | Discrete oscillator-domain choices available in one cognition→motor decision tick | Yes (PSC / COMPOSITE_MOTOR) |
| **S_phys** — physical emission space | Set of anonymous 6-band energy vectors that one body can inject into LPS as one emission on one scientific emission tick | Indirect: via body continuous controls `(osc_freq_u, osc_amp_u)` + pose |
| **S_recv** — receiver-distinguishable space | Set of A5 `osc_l_0..5` / `osc_r_0..5` vectors a listener can obtain after LPS + phenotype | No control of other’s emission; own reception is physics |

**Guiding distinction:** counting “signals” is only valid for finite discrete sets. `S_phys` is a **2-dimensional continuous manifold** embedded in `R^6`. Do not invent a finite vocabulary size for it.

---

## 1. Causal chain (Acanthostega)

```
COMPOSITE_MOTOR / legacy OSC_* actions
  → apply_osc_motor_action (nudge osc_freq_u / osc_amp_u; OSC_EMIT sets osc_emit_remaining)
  → body pose integrate
  → tick += 1
  → LPS step_end_of_tick(tick_now=T+1): if rem>0 → one PhysicalSignalEmission
       band_energies = band_profile(freq, amp) = amp · band_response(freq)
  → finite delay, range, inverse-quadratic attenuation, total-energy threshold
  → L/R receptor sampling (same shape × two distance scalars)
  → auditory buffer
  → auditory_fragments: osc_* = clip(energy / sensor_scale, 0, 1)
  → observation → A5 receipt (copy of cognition-bound osc_l/r)
```

Authoritative code:
- Motor: `oscillatory_signaling.apply_osc_motor_action`, `composite_motor.apply_composite_motor`
- Spectrum: `local_physical_signal_transport.band_profile` → `oscillatory_signaling.band_response`
- Transport: `step_end_of_tick` / `evaluate_wavefront_crossing_at_point` / `attenuation`
- Phenotype: `auditory_fragments` (`sensor_scale`, default 2.0)

Timing note: decision at scientific tick `T` that sets `OSC_EMIT` produces an LPS emission with `emission_tick=T` when `step_end_of_tick` runs after `tick` advances to `T+1`. Do not count each active remainder tick as a new motor “word”; remainder is duration state (Observer note already exists in serialize).

---

## 2. S_motor — motor-selectable repertoire (one decision tick)

### 2.1 Atomic actions
`OSC_FREQ_UP`, `OSC_FREQ_DOWN`, `OSC_AMP_UP`, `OSC_AMP_DOWN`, `OSC_EMIT`  
(documented in `mechanism_configuration` / `PHYSICAL_OSCILLATORY_SIGNALING.md`)

### 2.2 COMPOSITE_MOTOR_V1 factorization
In one decision cycle the oscillator domain is three independent picks:
- `frequency_delta ∈ {-1, 0, +1}`
- `amplitude_delta ∈ {-1, 0, +1}`
- `emit_trigger ∈ {false, true}`

**Finite oscillator-domain repertoire size:** `3 × 3 × 2 = 18` combinations per tick  
(when all five OSC actions are in `available`).

Apply order (same tick): freq nudge → amp nudge → emit gate.  
So an emit in the same tick uses **post-nudge** `(osc_freq_u, osc_amp_u)`.

### 2.3 What motor does *not* select
- No direct 6-band vector
- No continuous free `(f, a)` in one action (organism path is ±`freq_step` / ±`amp_step`)
- No independent duration knob (duration derived from `osc_amp_u` at `OSC_EMIT` time)
- Pose is locomotion domain, not oscillator domain (affects emission origin, not band shape)

### 2.4 Continuous body controls (state, not per-tick alphabet)
| Control | Range | Step (organism) | Default |
|---------|-------|-----------------|---------|
| `osc_freq_u` | `[0, 1]` clamp | `freq_step = 0.08` | `0.5` |
| `osc_amp_u` | `[0, 1]` clamp | `amp_step = 0.08` | `0.5` |
| `osc_emit_remaining` | integer ticks | set by emit; −1 per emission tick | `0` |

**Duration on emit:**  
`duration = clamp(round(duration_base · (0.5 + 0.5·amp_u)), duration_min, duration_max)`  
Defaults: `duration_base=8`, min=1, max=48 → for `amp_u∈[0,1]` realized duration ∈ **{4,5,6,7,8}** only.  
`OSC_EMIT` sets `remaining = max(existing_remaining, duration)` (refresh/extend).

**Organism-reachable lattice (from default 0.5, ± steps + clamp):**  
simple coset `0.5 + k·0.08` clamped → **15** distinct values.  
Long-horizon nudging after hitting `{0,1}` introduces additional cosets (BFS reachable set larger, ~39).  
Experimenter/`set_undercover_osc_params` may set continuous values outside the motor lattice — **not** organism `S_motor`.

**Verdict (motor):** agent chooses among a **finite discrete oscillator repertoire (18/tick)** that nudges a **2D continuous control state** on a **step lattice**. It does **not** pick from a finite set of named spectral “signals.”

---

## 3. S_phys — physical emission space (one emission tick)

When `osc_emit_remaining > 0` and oscillatory emission enabled, LPS creates **exactly one** endogenous emission per body per processed tick:

\[
\mathbf{b}(f,a) = a \cdot \mathbf{w}(f) \in \mathbb{R}^{6}_{\ge 0}
\]

with:
- `f = f_min + (f_max−f_min)·osc_freq_u` (defaults: identity map on `[0,1]`)
- `a = clamp(osc_amp_u, 0, source_cap)` (`source_cap=1`)
- \(\mathbf{w}(f)_i = \exp\!\big(-\tfrac12 ((c_i−f)/band\_width)^2\big)\),  
  `c = linspace(0,1,6)`, `band_width=0.22`  
  (overlapping Gaussians; **sum not normalized**)

Also attached physically (not in band vector): emission origin `(x,y)` = body pose at emission tick.

### 3.1 Dimensionality
- Controllable spectral DoF for OSC motor: **2** (`f`, `a`)
- Embedding dimension: **6** (bands)
- Image of \((f,a)\mapsto a\cdot w(f)\): a **2-dimensional manifold** (scaled curve) in \(\mathbb{R}^6\), not a 6D box
- Full \(\mathbb{R}^6_{\ge 0}\) band orthant is **not** reachable by OSC_EMIT (researcher `band_energies` / contact acoustics can leave this manifold)

### 3.2 Intensity vs spectral shape
| Question | Answer |
|----------|--------|
| Can the agent control **intensity**? | **Yes** — `osc_amp_u` scales all bands uniformly |
| Can the agent control **spectral shape**? | **Yes, but only via 1 parameter** — `osc_freq_u` slides the Gaussian bump across bands |
| Can the agent set arbitrary band mix? | **No** (OSC path) |
| Fixed finite timbre table? | **No** — continuous (or lattice-sampled) family, not a catalog of presets |

Example shapes (`a=1`):

| f | w (approx) | ∑w |
|---|------------|-----|
| 0.0 | (1.00, 0.66, 0.19, 0.02, 0.00, 0) | 1.88 |
| 0.5 | (0.08, 0.39, 0.90, 0.90, 0.39, 0.08) | 2.74 |
| 1.0 | (0, 0.00, 0.02, 0.19, 0.66, 1.00) | 1.88 |

### 3.3 Finite power?
- Continuous \((f,a)\): **infinite** cardinality; report **dim = 2** + clamps
- Organism lattice at emission instant: at most \(|L_f|·|L_a|\) distinct band vectors (order ~15² if both on the simple 0.5-coset; more if long-horizon cosets) — still a **sampling of the same 2D family**, not independent signals
- Per decision tick motor alphabet: **18** (finite) — this is `S_motor`, not `|S_phys|`

### 3.4 Mid-episode modulation
While `remaining > 0`, later ticks keep emitting with **current** `(freq_u, amp_u)`. Agent may nudge parameters without re-triggering emit → physical trajectory through the 2D manifold over time. Duration countdown is independent of those nudges (except new `OSC_EMIT` refresh).

---

## 4. LPS maps that collapse or preserve distinctions

Medium defaults (`UniformSignalMediumConfig`):  
`propagation_speed=2`, `attenuation_coefficient=0.08`, `maximum_range=8`, `reception_threshold=0.03`, `sensor_scale=2`, `noise_floor=0`.

### 4.1 Distance attenuation (shape-preserving scale)
`att(d) = 1 / (1 + k d²)` applied **uniformly** to all bands.  
For a **single** source, relative band ratios are invariant to distance; only intensity scales.

### 4.2 Hard collapses
1. **Range:** `d > maximum_range` → rejection → no A5 contribution from that emission  
2. **Threshold:** `∑_i b_i · att(d) < reception_threshold` → rejection → all bands absent (silence), not a scaled copy  
   - Near field (`att≈1`, `f=0.5`): amp ≲ **0.011** collapses to nothing  
   - At `d=8` (`att≈0.16`): amp ≲ **0.067** collapses  
3. **Missed wavefront / delay:** reception only on crossing ticks; wrong place/time → silence  
4. **Capacity:** `max_active_emissions` reject (rare under normal load)

### 4.3 Soft collapses / ambiguities
1. **Intensity–distance confounding:** `(a1, d1)` vs `(a2, d2)` with `a1·att(d1)=a2·att(d2)` and same `f` → identical band vectors at a mono point (and proportional L/R if geometry scales similarly)  
2. **Phenotype clip:** `osc = min(1, energy/sensor_scale)`  
   - Single OSC emission at `a≤1` does **not** drive a band to the ceiling (`peak ≈ 0.45 < 1` at self-receptor)  
   - **Superposition** of multiple emissions / other acoustic mechanisms can saturate → loses intensity above scale; can also distort shape if only some bands clip  
3. **L/R:** one emission → same shape × `(α_L, α_R)`; differences are geometric, not independent spectra  
4. **Aggregation:** concurrent receptions **sum** in the auditory buffer → reconstructed shape need not lie on the OSC 2D manifold (mixture)  
5. **Self vs foreign:** no identity channel; only anonymous energy

### 4.4 What A5 can still discriminate (in principle)
For an isolated OSC source above threshold, below clip:
- **Spectral family parameter** near `f` (6-band pattern along the curve `w(f)`)
- **Intensity scale** `a·att(d)` (confounded with distance)
- **Left/right imbalance** (geometry / heading), not source bearing as an explicit variable

A5 cannot recover: exact `osc_freq_u`, exact `a`, source id, exact distance, motor provenance, or Section B phenotype stamp fields as cognition inputs.

---

## 5. S_recv — receiver-distinguishable space (A5)

### 5.1 Observation dimensionality
12 continuous channels in `[0,1]`: `osc_l_0..5`, `osc_r_0..5` after phenotype.

### 5.2 Image of one isolated OSC emission
If accepted and unclipped:
\[
(\mathbf{L},\mathbf{R}) = \big(a\cdot\mathrm{att}(d_L)\cdot\mathbf{w}(f),\; a\cdot\mathrm{att}(d_R)\cdot\mathbf{w}(f)\big)/s
\]
with `s=sensor_scale`.  
So again a low-dimensional family (parameters: `f`, `a`, pose/heading geometry), embedded in `[0,1]^{12}`.

### 5.3 Many-to-one maps into A5
| Upstream difference | Survives to A5? |
|---------------------|-----------------|
| Δf along manifold (above threshold) | Usually yes (shape) |
| Δa at fixed pose | Yes until clip/threshold |
| Δa compensated by Δd | **No** (intensity confound) |
| Amp below threshold vs silence | **No** (both → zeros) |
| Distinct motor lattice points that map to near-identical `w(f)` | Weakly / noise-free continuous model: distinguishable in R^6; practically may be near-collinear for small Δf given `band_width=0.22` overlap |
| Researcher arbitrary 6-band vs OSC manifold vector | Yes if shapes differ; OSC agent cannot emit the arbitrary one |

---

## 6. Direct answers

### 6.1 Exact physical signal space one agent can create in one scientific emission tick
**Continuous 2-parameter family** of non-negative 6-vectors  
`b = a · w(f)`, `f,a ∈ [0,1]` (clamped), plus emission pose.  
**Not** a finite codebook. Dimensionality **2** in band space (plus continuous pose in the world).

### 6.2 Intensity / spectrum control vs fixed repertoire
- **Intensity:** controllable (`osc_amp_u`), continuous/lattice, uniform band scale  
- **Spectral shape:** controllable only as **one frequency coordinate** through fixed overlapping Gaussians — **not** independent multi-band synthesis  
- **Per-tick motor alphabet:** fixed **finite** 18-way oscillator factor choices that *adjust* the continuous controls / gate emit — this is **not** the same as a fixed set of physical spectra

### 6.3 Independent controllable DoF (OSC endogenous emission)
| Layer | Independent DoF |
|-------|-----------------|
| Motor pick / tick | 3 discrete factors (freq Δ, amp Δ, emit) |
| Body emission controls | 2 continuous (`freq_u`, `amp_u`) + integer remaining |
| Physical band vector | 2 (manifold); **not** 6 |
| Duration | **0** independent (tied to amp at emit; refresh only) |

### 6.4 Theoretical power
| Object | Power |
|-------|-------|
| `S_motor` oscillator domain / tick | **18** (finite) |
| Duration values at emit | **5** (`{4..8}`) under defaults |
| Simple freq or amp lattice from default | **15** each |
| `S_phys` band vectors | **Infinite** (dim 2); lattice sampling finite but still 2D family |
| `S_recv` full `[0,1]^12` | Not filled by one OSC source; isolated image is low-dimensional |

---

## 7. Preservation / anti-claims

- No mechanics changed by this audit  
- Does **not** claim language, messages, symbols, or “how many words”  
- Does **not** treat contact/impact acoustics as OSC motor repertoire  
- Does **not** treat researcher free-band injection as organism expressivity  
- A5 remains anonymous post-phenotype pre-cognition energy

---

## 8. Recommended next seams (architecture only)

1. **Quantitative manifold separation:** metric on `w(f)` vs `band_width` — how small Δf remains linearly separable at A5 after attenuation  
2. **SAV3 comparison:** selected-organism A5 vs passive probe for the same OSC emission (already roadmap-adjacent)  
3. If a future design wanted full 6-band motor control, that would be a **new mechanism version** — explicitly out of current OSC_EMIT expressivity

---

## Machine-readable summary

```
AUDIT_ID = OSC_EMISSION_EXPRESSIVITY_AND_RECEIVER_DISCRIMINABILITY_AUDIT
MECHANICS_CHANGED = false
SEMANTICS_INVESTIGATED = false
PATH = action/PSC → OSC_* → (osc_freq_u,osc_amp_u,rem) → LPS band_profile → attenuation/threshold → A5 osc_l/r
S_MOTOR_OSC_COMBOS_PER_TICK = 18
S_MOTOR_CONTINUOUS_CONTROLS = 2
S_PHYS_BAND_DOF = 2
S_PHYS_BAND_DIM_AMBIENT = 6
S_PHYS_IS_FINITE_CODEBOOK = false
S_PHYS_MANIFOLD = a*w(f)_overlapping_gaussian_6
INTENSITY_CONTROLLABLE = true
SPECTRAL_SHAPE_CONTROLLABLE = true_via_single_freq_parameter
ARBITRARY_6BAND_SHAPE_CONTROLLABLE = false
DURATION_INDEPENDENT_DOF = false
DURATION_VALUES_DEFAULT = [4,5,6,7,8]
FREQ_STEP = 0.08
AMP_STEP = 0.08
SOURCE_CAP = 1.0
SENSOR_SCALE = 2.0
RECEPTION_THRESHOLD = 0.03
ATTENUATION = 1/(1+k*d^2)
SINGLE_EMISSION_PHENOTYPE_CEILING_HIT = false
PRIMARY_COLLAPSES = threshold_silence, range_reject, intensity_distance_confound, superposition_clip
NEXT_SAFE_SEAM = QUANTITATIVE_W_F_SEPARABILITY_OR_SAV3_COMPARISON
```
