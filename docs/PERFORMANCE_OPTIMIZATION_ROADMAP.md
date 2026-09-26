# Performance optimization roadmap

Derived strictly from `results/performance_architecture/` on this machine. Do not reorder based on intuition.

## NOW (accepted)

1. **Execution modes LIVE / FAST / MAX / HEADLESS** with sim clock ≠ Observer clock.
2. **Process-parallel Search workers** — near-linear to ~4 workers; still useful at 8 with efficiency drop.
3. **Benchmark + fingerprint harness** — `experiments/run_long_run_performance_architecture.py`.

## NEXT (highest measured ROI)

### 1. PSC / cognition hot path

cProfile shows `run_cognition_before_action` and `predict_one_step` dominate single-world wall time when cognition is on.

- Pack trajectory / feature state toward SoA for the inner predict loop.
- Optional **Numba** on packed numeric core *only* with EXACT_MATCH gate + Python fallback.
- Do **not** change cognition cadence or PSC semantics for speed.

### 2. Scientific Telemetry V2 SIM-path cost

When the writer is open, V2 append + event/motion bookkeeping is a large fraction of HEADLESS session time vs bare `runtime.step`.

- Keep Analyzer-required evidence.
- Safe directions: batched flush (already partially present), thinner SEARCH_COMPACT rows for workers, async finalize — all with equivalence proofs.
- Rejected Search worlds must not be forced to write full multi-GB biographies.

### 3. Live presentation cost

Full LIVE stack (step + compact capture) is several× slower than HEADLESS. Already mitigated by async capture + mode presets; keep MAX/HEADLESS free of per-tick renders.

## THEN

- **NumPy** on grid/OSC fields if/when those stages rise in profile share (today they are small vs cognition on the default Tiktaalik bench).
- Data-layout boundaries: coexist packed arrays with scientific objects at perception/field edges.

## LATER

- **GPU batch kernels** for `[world,y,x,*]` fields across many Search worlds — only after CPU layout work and when batch size amortizes transfer. GTX 1650 4GB: see `gpu_memory_estimate.json` (conservative capacity for field SoA only).
- Bit-exact **snapshot/resume** (blockers in `snapshot_readiness.json`).

## Explicit non-goals (this phase)

- No tick skipping, dt changes, silent mechanism disable, or cadence cuts.
- No mandatory Numba/GPU runtime dependency.
- No broad rewrite without EXACT_MATCH.

## Suggested implementation order

```
NOW:  CPU multiprocessing Search workers + modes (done)
NEXT: PSC predict_one_step packing (± Numba) with fingerprint gate
THEN: V2 SEARCH_COMPACT writer path for workers
LATER: NumPy fields → GPU batch if Search batch justifies it
```
