# ACANTHOSTEGA · BETA4 PERFORMANCE BENCHMARK REBASE AND INSTRUMENTATION V1 (P0)

## Identity
- Schema: `BETA4_PERFORMANCE_BENCHMARK_V1`
- Capability: `beta4_performance_benchmark`
- Profile: `COMPARABLE_SCIENTIFIC_SERVER_BROWSER_ANALYZER_TIMING_P0_V1`
- Authority: `RESEARCHER_PERFORMANCE_TELEMETRY_NON_PHYSICAL`

## Verdict
**C. P0_PARTIAL_BROWSER_PROFILE_UNAVAILABLE**

Instrumentation is disabled by default (`PSY_BETA4_PERF_BENCH=1` or `beta4_performance_benchmark.enable()`).
It does not enter cognition, snapshots, or physical fingerprints.

Comparable scientific/server baselines are under `results/beta4_performance_benchmark_rebase_and_instrumentation_v1/`.
Browser Observer profiles remain `NOT_MEASURED` pending an isolated browser harness.

## Next safe seam
`P1_INACTIVE_OBSERVER_PAYLOAD_AND_RENDER_SUSPENSION`
