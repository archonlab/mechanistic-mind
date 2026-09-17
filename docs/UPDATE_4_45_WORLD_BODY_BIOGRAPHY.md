# Update 4.45 FINAL REPORT — World–Body Co-development

## Outcome E

Different temporal pairings of the same world-state and body-state
marginals produced different bounded W. Under PRESENT-2 (q/I/N reset,
W kept) the same probe regenerated history-specific q, I, and N.

Motor difference is **not** supported (ΔP(A) ≈ 0.0057 < 0.01). Readout
was not changed. This matches the 4.44 motor-orthogonal boundary.

29 / 32 claims ASSERTED. Seeds 17, 23, 41, 59, 83. `leak = []`

## What was acquired

Not a biography list. The existing 4.41 rule saw world on channel 0 and
body on channel 1 as sequential numeric pulses. H_COUPLED_A pairs like
with like; H_COUPLED_B swaps high/low. Exact matched counts.

    L1(W_A, W_B) = 0.0759 (all seeds)
    q traj L1    = 0.294
    I traj L1    = 0.857
    N traj L1    = 0.339

World-only and body-only do not reproduce the coupled effect
(dq vs those ≈ 1.03–1.05).

## NOT ASSERTED

- **C20** shuffled vs coupled: seed 41 q L1 = 0.0997, just under 0.10.
  Other seeds 0.13–0.16. Pairing A vs B remains distinguishable (C21).
- **C25** body-trajectory-alone did not fully replicate the 4.44 null
  under this joint-input construction.
- **C27** motor. Do not retune.

## First unsupported arrows

| chain | first unsupported |
|---|---|
| WORLD_PHYSICS | null |
| BODY_PHYSICS | null |
| ACQUISITION | null |
| JOINT_RELATION | null |
| PERSISTENCE | null |
| PRESENT_REGENERATION | null |
| REVISION | null |
| MOTOR | C27_motor |
| FULL_BIOGRAPHICAL_CHAIN | C27_motor |

## Strongest allowed claim

Different developmental relations between external physical processes and
the organism's own body-state trajectories produced persistent acquired
internal structure. Under matched present world/body conditions, the same
probe regenerated history-specific endogenous dynamics after removable raw
history and transient state were controlled.

Shorter: past world-body co-development altered present endogenous dynamics.

Not claimed: autobiographical memory, self, identity, body ownership,
subjective past, preference, motivation.

## Architecture

Body does not enter `step()` by itself. 4.45 only constructs `u` as
`(world, 0, 0)` then `(0, body, 0)`. Learning rule unchanged. Ablating
either channel removes the joint effect. No raw-history lookup.

## Historical NULLs

4.42 = C, 4.43 = D, 4.44 = A. Motor readout untouched.

## Next question (not implemented)

Smallest next ask: why joint-structure ΔN still fails to move P(A) — the
same readout-orthogonality as 4.44. Do not add gain, reward, or self-model.

Do not implement 4.46 in this update.
