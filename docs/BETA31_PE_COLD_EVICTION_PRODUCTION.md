# Beta 3.1 PE cold eviction productionization

Seed 575. Existing PECA eviction reused. Persistence representation only. GIT_PUSH = NO.

## Result

`BETA31_PE_COLD_EVICTION_PRODUCTION = PASS`

Canonical Beta 3.1 default is ON (`_COLD_ARCHIVE = True`, `_COLD_EVICT = True`, chunk 256, no mmap). Beta 3 reference untouched.

Open-chunk checkpoint uses PECA sidecars (`pe_open/*.peca`); JSON no longer copies unsealed float arrays. Aged 5k and 10k checkpoint/restore continuation were EXACT. 40k completed without OOM (644.59 MB RSS vs prior ~18.2 GB).

Full measured block: `results/beta31_pe_cold_eviction_production/summary.json`.
Aged checkpoint details: `docs/BETA31_PE_AGED_CHECKPOINT_RESTORE.md`.
40k: `docs/BETA31_PE_40K_VALIDATION.md`.
