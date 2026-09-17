#!/usr/bin/env python3
"""MM-EXP-4 — GAP REDISTRIBUTION × SECOND-EXPOSURE FLUX
ZERO production change. Observer-side tick accounting only.
"""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import hashlib, json
import numpy as np

from mechanistic_mind.planet.config import default_planet_config
from mechanistic_mind.planet.state import initialize_planet
from mechanistic_mind.planet.dynamics import step_planet
from mechanistic_mind.physical_body.config import default_physical_body2_config
from mechanistic_mind.physical_body.state import initialize_physical_body
from mechanistic_mind.physical_body.dynamics import step_physical_body
from mechanistic_mind.internal_medium.config import default_internal_medium_config
from mechanistic_mind.internal_medium.state import initialize_internal_medium
from mechanistic_mind.internal_medium.flux import (
    step_internal_medium, compute_medium_fluxes, apply_medium_fluxes,
)

ROOT = Path('results/mm_exp4_gap_redistribution_second_exposure_flux')
ROOT.mkdir(parents=True, exist_ok=True)

SEEDS = [17, 23, 41]
WARM = 80
EXP_DUR = 10
GAP_CONTIG = 0
GAP_SPACED = 20
FUT = 120
FUT_SEED = 59
MAT_AMP = 0.08
THERM_AMP = 0.08
POSE_SHIFT = 1.0
NUM_FLOOR = 1e-12
PHYS_FRAC = 0.05
ACCT_TOL = 1e-9

PAIRS = {
    'SAME_MAT': ('MAT0', 'MAT1'),
}

# ---------- freeze hash ----------
PROD = []
for folder in ('physical_body', 'planet', 'internal_medium', 'internal_substrate'):
    p = Path('mechanistic_mind') / folder
    if p.exists():
        PROD += sorted(p.glob('*.py'))
FREEZE = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in PROD}
FREEZE_OK = True

# ---------- helpers ----------

def om_vec(body, medium):
    return np.concatenate([body.B.copy(), body.B_core.copy(), [body.T], medium.c.sum(axis=0)])


def local_Mw(planet, body, bcfg):
    cells = body.cells(planet.T.shape[1], planet.T.shape[0], bcfg.footprint)
    n = max(1, len(cells))
    Mw = np.zeros(3)
    for iy, ix in cells:
        Mw += planet.M[:, iy, ix]
    return Mw / n, cells


def observer_J(planet, body, bcfg):
    """Exact material flux law from dynamics.py (pre-step intent)."""
    Mw, cells = local_Mw(planet, body, bcfg)
    J = np.zeros(3)
    for i, perm in enumerate(bcfg.permeability):
        flux_i = float(perm) * (float(Mw[i]) - float(body.B[i]))
        if flux_i > 0:
            avail = float(sum(planet.M[i, iy, ix] for iy, ix in cells))
            flux_i = min(flux_i, avail)
        else:
            flux_i = -min(-flux_i, float(body.B[i]))
        # clip to B_max after add is separate; intent flux:
        newB = float(np.clip(body.B[i] + flux_i, 0.0, bcfg.B_max))
        flux_i = newB - float(body.B[i])
        J[i] = flux_i
    return J, Mw


def sequential_B_ops(planet, body, bcfg):
    """Observer sequential reconstruction of B writers inside step_physical_body.
    Returns dict of B deltas and reconstructed B after body ops (pre-medium).
    """
    b = deepcopy(body)
    pl = deepcopy(planet)
    h, w = pl.T.shape
    cells = b.cells(w, h, bcfg.footprint)
    ncell = max(1, len(cells))
    T_w = float(sum(pl.T[iy, ix] for iy, ix in cells) / ncell)
    Mw = np.zeros(3)
    for iy, ix in cells:
        Mw += pl.M[:, iy, ix]
    Mw /= ncell

    out = {}
    B0 = b.B.copy()

    # thermal (may change T only)
    if bcfg.thermal_enabled:
        flux = bcfg.thermal_conductance * (T_w - b.T)
        dTb = flux / bcfg.heat_capacity
        b.T = float(np.clip(b.T + dTb, bcfg.T_min, bcfg.T_max))
        if bcfg.thermal_backreact:
            share = bcfg.thermal_backreact * flux / ncell
            for iy, ix in cells:
                pl.T[iy, ix] = float(np.clip(
                    pl.T[iy, ix] - share / max(float(pl.capacity[iy, ix]), 1e-6), 0.0, 1.0))
    out['dB_thermal'] = b.B.copy() - B0  # zeros

    # material
    Bm = b.B.copy()
    J = np.zeros(3)
    clip_mat = False
    if bcfg.material_enabled:
        for i, perm in enumerate(bcfg.permeability):
            flux_i = float(perm) * (float(Mw[i]) - float(b.B[i]))
            if flux_i > 0:
                avail = float(sum(pl.M[i, iy, ix] for iy, ix in cells))
                flux_i = min(flux_i, avail)
            else:
                flux_i = -min(-flux_i, float(b.B[i]))
            newB = float(np.clip(b.B[i] + flux_i, 0.0, bcfg.B_max))
            if abs(newB - (b.B[i] + flux_i)) > 1e-15:
                clip_mat = True
            J[i] = newB - float(b.B[i])
            b.B[i] = newB
            if bcfg.material_backreact and abs(J[i]) > 0:
                per = J[i] / ncell
                for iy, ix in cells:
                    pl.M[i, iy, ix] = float(max(0.0, float(pl.M[i, iy, ix]) - per))
    out['dB_world'] = b.B.copy() - Bm
    out['J'] = J
    out['Mw'] = Mw
    out['clip_mat'] = clip_mat

    # core
    Bc0 = b.B.copy()
    dBc_core = np.zeros(3)
    if bcfg.core_enabled:
        for i in range(3):
            df = bcfg.core_exchange * (float(b.B[i]) - float(b.B_core[i]))
            if df > 0:
                df = min(df, float(b.B[i]))
            else:
                df = -min(-df, float(b.B_core[i]))
            b.B[i] = float(np.clip(b.B[i] - df, 0.0, bcfg.B_max))
            b.B_core[i] = float(np.clip(b.B_core[i] + df, 0.0, bcfg.B_max))
            dBc_core[i] = df
    out['dB_core'] = b.B.copy() - Bc0
    out['dBc_from_core'] = dBc_core

    # reaction
    Br = b.B.copy()
    consumed = 0.0
    if bcfg.reaction_enabled:
        rate = bcfg.react_rate * float(np.clip(b.T, 0.0, 1.0))
        consumed = rate * min(float(b.B[0]), float(b.B[1]))
        b.B[0] -= consumed
        b.B[1] -= consumed
        b.B[2] = float(np.clip(b.B[2] + consumed, 0.0, bcfg.B_max))
        b.T = float(np.clip(b.T + bcfg.react_heat * consumed, bcfg.T_min, bcfg.T_max))
    out['dB_reaction'] = b.B.copy() - Br
    out['consumed'] = consumed

    out['B_after_body'] = b.B.copy()
    out['body_recon'] = b
    out['planet_recon'] = pl
    return out


def impose(planet, body, tag, cells, pcfg, doses):
    if tag == 'MAT0':
        for iy, ix in cells:
            planet.M[0, iy, ix] += MAT_AMP
        doses['MAT0'] = doses.get('MAT0', 0.0) + MAT_AMP * len(cells)
    elif tag == 'MAT1':
        for iy, ix in cells:
            planet.M[1, iy, ix] += MAT_AMP
        doses['MAT1'] = doses.get('MAT1', 0.0) + MAT_AMP * len(cells)
    elif tag == 'THERM':
        for iy, ix in cells:
            planet.T[iy, ix] = float(np.clip(planet.T[iy, ix] + THERM_AMP, 0.0, 1.0))
        doses['THERM'] = doses.get('THERM', 0.0) + THERM_AMP * len(cells)
    elif tag == 'POSE':
        body.x = float((body.x + POSE_SHIFT) % pcfg.width)
        doses['POSE'] = doses.get('POSE', 0.0) + abs(POSE_SHIFT)


def warm_and_frames(seed):
    pcfg = default_planet_config()
    bcfg = default_physical_body2_config()
    bcfg.displacement_enabled = False
    mcfg = default_internal_medium_config()
    planet = initialize_planet(pcfg, seed=seed)
    body = initialize_physical_body(bcfg, width=pcfg.width, height=pcfg.height)
    medium = initialize_internal_medium(mcfg)
    for _ in range(WARM):
        step_planet(planet, pcfg, seed=seed)
        step_physical_body(body, planet, bcfg)
        step_internal_medium(medium, body, mcfg)
    horizon = EXP_DUR * 2 + GAP_SPACED + FUT + 5
    ref_p, ref_b, ref_m = deepcopy(planet), deepcopy(body), deepcopy(medium)
    frames = []
    for _ in range(horizon):
        frames.append(deepcopy(ref_p))
        step_planet(ref_p, pcfg, seed=seed)
        step_physical_body(ref_b, ref_p, bcfg)
        step_internal_medium(ref_m, ref_b, mcfg)
    return pcfg, bcfg, mcfg, body, medium, frames


def run_branch(tags, gap, frames, body0, medium0, pcfg, bcfg, mcfg, instrument=True):
    body = deepcopy(body0)
    medium = deepcopy(medium0)
    doses = {'MAT0': 0.0, 'MAT1': 0.0, 'THERM': 0.0, 'POSE': 0.0}
    ticks = []
    t = 0
    phases = (['first'] * EXP_DUR) + (['gap'] * gap) + (['second'] * EXP_DUR)

    for phase in phases:
        pl = deepcopy(frames[t])
        tag = None
        if phase == 'first':
            tag = tags[0]
        elif phase == 'second':
            tag = tags[1]
        cells = body.cells(pcfg.width, pcfg.height, bcfg.footprint)
        if tag is not None:
            impose(pl, body, tag, cells, pcfg, doses)

        rec = {
            't': t, 'phase': phase, 'tag': tag,
            'B_pre': body.B.copy(), 'Bc_pre': body.B_core.copy(), 'T_pre': body.T,
            'c_pre': medium.c.copy(),
        }
        if instrument:
            ops = sequential_B_ops(pl, body, bcfg)
            rec['J'] = ops['J']
            rec['Mw'] = ops['Mw']
            rec['dB_world_pred'] = ops['dB_world']
            rec['dB_core_pred'] = ops['dB_core']
            rec['dB_reaction_pred'] = ops['dB_reaction']
            rec['clip_mat'] = ops['clip_mat']
            # medium fluxes on reconstructed post-body state
            btmp = ops['body_recon']
            mtmp = deepcopy(medium)
            fl = compute_medium_fluxes(mtmp, btmp, mcfg)
            rec['dB_medium_pred'] = fl.dB.copy()
            B_recon = ops['B_after_body'] + fl.dB
            B_recon = np.clip(B_recon, 0.0, mcfg.C_max)
            rec['B_recon_next'] = B_recon

        # actual step
        step_physical_body(body, pl, bcfg)
        step_internal_medium(medium, body, mcfg)

        rec['B_post'] = body.B.copy()
        rec['Bc_post'] = body.B_core.copy()
        rec['T_post'] = body.T
        rec['c_post'] = medium.c.copy()
        rec['dB_actual'] = rec['B_post'] - rec['B_pre']
        if instrument:
            rec['recon_err'] = float(np.linalg.norm(rec['B_post'] - rec['B_recon_next']))
        ticks.append(rec)
        t += 1

    end = {
        'body': deepcopy(body), 'medium': deepcopy(medium), 't': t,
        'om': om_vec(body, medium), 'doses': doses,
    }
    return ticks, end


def phase_slice(ticks, name):
    return [x for x in ticks if x['phase'] == name]


def analyze_pair(seed, gap, tags=('MAT0', 'MAT1')):
    pcfg, bcfg, mcfg, body0, medium0, frames = warm_and_frames(seed)
    # DET duplicate
    t1, e1 = run_branch(tags, gap, frames, body0, medium0, pcfg, bcfg, mcfg)
    t1b, e1b = run_branch(tags, gap, frames, body0, medium0, pcfg, bcfg, mcfg)
    det_dup = float(np.linalg.norm(e1['om'] - e1b['om']))

    ticks_AB, end_AB = run_branch(tags, gap, frames, body0, medium0, pcfg, bcfg, mcfg)
    tags_BA = (tags[1], tags[0])
    ticks_BA, end_BA = run_branch(tags_BA, gap, frames, body0, medium0, pcfg, bcfg, mcfg)

    Om0 = float(np.linalg.norm(end_AB['om'] - end_BA['om']))
    Om0_B = float(np.linalg.norm(end_AB['body'].B - end_BA['body'].B))
    rA = float(np.linalg.norm(end_AB['om']))
    rB = float(np.linalg.norm(end_BA['om']))
    phys_ref = PHYS_FRAC * max(rA, rB)

    # post-first / pre-second
    first_AB = phase_slice(ticks_AB, 'first')
    first_BA = phase_slice(ticks_BA, 'first')
    gap_AB = phase_slice(ticks_AB, 'gap')
    gap_BA = phase_slice(ticks_BA, 'gap')
    sec_AB = phase_slice(ticks_AB, 'second')
    sec_BA = phase_slice(ticks_BA, 'second')

    B_post1_AB = first_AB[-1]['B_post']
    B_post1_BA = first_BA[-1]['B_post']
    dB_post1 = B_post1_AB - B_post1_BA
    n_post1 = float(np.linalg.norm(dB_post1))

    if gap > 0:
        B_pre2_AB = gap_AB[-1]['B_post']
        B_pre2_BA = gap_BA[-1]['B_post']
        Bc_pre2_AB = gap_AB[-1]['Bc_post']
        Bc_pre2_BA = gap_BA[-1]['Bc_post']
        c_pre2_AB = gap_AB[-1]['c_post']
        c_pre2_BA = gap_BA[-1]['c_post']
        T_pre2_AB = gap_AB[-1]['T_post']
        T_pre2_BA = gap_BA[-1]['T_post']
    else:
        B_pre2_AB = B_post1_AB
        B_pre2_BA = B_post1_BA
        Bc_pre2_AB = first_AB[-1]['Bc_post']
        Bc_pre2_BA = first_BA[-1]['Bc_post']
        c_pre2_AB = first_AB[-1]['c_post']
        c_pre2_BA = first_BA[-1]['c_post']
        T_pre2_AB = first_AB[-1]['T_post']
        T_pre2_BA = first_BA[-1]['T_post']

    dB_pre2 = B_pre2_AB - B_pre2_BA
    n_pre2 = float(np.linalg.norm(dB_pre2))

    # cosine
    if n_post1 > NUM_FLOOR and n_pre2 > NUM_FLOOR:
        cos_th = float(np.dot(dB_post1, dB_pre2) / (n_post1 * n_pre2))
    else:
        cos_th = float('nan')

    # component weights
    w_post = (dB_post1 / n_post1).tolist() if n_post1 > NUM_FLOOR else [0, 0, 0]
    w_pre = (dB_pre2 / n_pre2).tolist() if n_pre2 > NUM_FLOOR else [0, 0, 0]

    # gap operator contributions to ΔB change
    gap_ops = {'world': np.zeros(3), 'core': np.zeros(3), 'reaction': np.zeros(3), 'medium': np.zeros(3)}
    recon_errs = []
    gap_traj = []
    for a, b in zip(gap_AB, gap_BA):
        dB = a['B_post'] - b['B_post']
        gap_traj.append({
            't': a['t'],
            'dB': dB.tolist(),
            'norm': float(np.linalg.norm(dB)),
            'dBc': (a['Bc_post'] - b['Bc_post']).tolist(),
            'dT': float(a['T_post'] - b['T_post']),
        })
        gap_ops['world'] += a['dB_world_pred'] - b['dB_world_pred']
        gap_ops['core'] += a['dB_core_pred'] - b['dB_core_pred']
        gap_ops['reaction'] += a['dB_reaction_pred'] - b['dB_reaction_pred']
        gap_ops['medium'] += a['dB_medium_pred'] - b['dB_medium_pred']
        recon_errs.append(a['recon_err'])
        recon_errs.append(b['recon_err'])

    # second exposure fluxes
    J0_AB = sec_AB[0]['J']; J0_BA = sec_BA[0]['J']
    dJ0 = J0_AB - J0_BA
    n_dJ0 = float(np.linalg.norm(dJ0))
    # predicted from ΔB and p: ΔJ = -p * ΔB (componentwise) when Mw identical
    p = np.array(bcfg.permeability, dtype=float)
    # at pre-second, Mw from first second tick (after impose)
    Mw_AB = sec_AB[0]['Mw']; Mw_BA = sec_BA[0]['Mw']
    Mw_equal = float(np.linalg.norm(Mw_AB - Mw_BA)) < 1e-12
    # use pre-second B for prediction of initial J
    pred_J_AB = np.zeros(3); pred_J_BA = np.zeros(3)
    for i in range(3):
        pred_J_AB[i] = p[i] * (Mw_AB[i] - B_pre2_AB[i])
        pred_J_BA[i] = p[i] * (Mw_BA[i] - B_pre2_BA[i])
    # apply same clips approximately via measured J instead
    pred_dJ = -p * dB_pre2  # if Mw identical
    pred_err = float(np.linalg.norm(dJ0 - pred_dJ)) if Mw_equal else float('nan')

    D_recv2_AB = np.zeros(3); D_recv2_BA = np.zeros(3)
    flux_traj = []
    for a, b in zip(sec_AB, sec_BA):
        D_recv2_AB += a['J']; D_recv2_BA += b['J']
        flux_traj.append({
            't': a['t'],
            'J_AB': a['J'].tolist(), 'J_BA': b['J'].tolist(),
            'dJ': (a['J'] - b['J']).tolist(),
            'dJ_norm': float(np.linalg.norm(a['J'] - b['J'])),
            'dB': (a['B_post'] - b['B_post']).tolist(),
            'dB_norm': float(np.linalg.norm(a['B_post'] - b['B_post'])),
        })
    dRecv2 = D_recv2_AB - D_recv2_BA
    n_dRecv2 = float(np.linalg.norm(dRecv2))

    # full sequence operator budget on ΔB
    op_phase = {ph: {k: np.zeros(3) for k in ('world', 'core', 'reaction', 'medium')}
                for ph in ('first', 'gap', 'second')}
    for ticks, sign in ((ticks_AB, 1.0), (ticks_BA, -1.0)):
        for rec in ticks:
            ph = rec['phase']
            op_phase[ph]['world'] += sign * rec['dB_world_pred']
            op_phase[ph]['core'] += sign * rec['dB_core_pred']
            op_phase[ph]['reaction'] += sign * rec['dB_reaction_pred']
            op_phase[ph]['medium'] += sign * rec['dB_medium_pred']

    dB_final = end_AB['body'].B - end_BA['body'].B
    recon_dB = sum((op_phase[ph][k] for ph in op_phase for k in op_phase[ph]), np.zeros(3))
    R_full = dB_final - recon_dB
    # note: sequential non-additivity => R_full may be nonzero even if per-tick recon ok
    max_recon_err = max(recon_errs) if recon_errs else max(
        [x['recon_err'] for x in ticks_AB + ticks_BA])

    # projection: relevant for MAT1 second in AB is species1 channel; for BA second is species0
    # SAME_MAT: second exposure channel differs by order! AB second=MAT1, BA second=MAT0
    # Relevant susceptibility for each branch's own second channel:
    # For order residual on final B, multi-channel.
    # Preregistered projection L for "second exposure relevance" as:
    # L_k = p_k for all k (local sensitivity of J to B): coordinate |p · ΔB| and per-component
    L = p
    proj_post1 = float(np.dot(L, dB_post1))
    proj_pre2 = float(np.dot(L, dB_pre2))
    # channel-specific: for species that is "the other" material
    # Also report abs weighted: sum_k p_k |ΔB_k|
    sus_post1 = float(np.sum(np.abs(L * dB_post1)))
    sus_pre2 = float(np.sum(np.abs(L * dB_pre2)))

    # gap replay identity
    if gap > 0:
        # save post-first full state from AB, replay gap twice
        b_pf = deepcopy(end_AB['body'])  # wrong - need post first
        # reconstruct: after first phase
        bA = deepcopy(body0); mA = deepcopy(medium0); tt = 0
        for _ in range(EXP_DUR):
            pl = deepcopy(frames[tt]); impose(pl, bA, tags[0], bA.cells(pcfg.width, pcfg.height, bcfg.footprint), pcfg, {})
            step_physical_body(bA, pl, bcfg); step_internal_medium(mA, bA, mcfg); tt += 1
        s0 = (deepcopy(bA), deepcopy(mA), tt)
        def replay_gap(state):
            b, m, t0 = deepcopy(state[0]), deepcopy(state[1]), state[2]
            for _ in range(gap):
                pl = deepcopy(frames[t0]); step_physical_body(b, pl, bcfg); step_internal_medium(m, b, mcfg); t0 += 1
            return om_vec(b, m)
        g1 = replay_gap(s0); g2 = replay_gap(s0)
        gap_replay_err = float(np.linalg.norm(g1 - g2))
    else:
        gap_replay_err = 0.0

    # B swap at pre-second: swap B only between AB and BA, run second exposure
    def run_from_pre2(B_use, Bc_use, T_use, c_use, second_tag, t_start):
        b = deepcopy(body0); m = deepcopy(medium0)
        # advance to t_start with dummy? better clone from instrumented
        b.B = B_use.copy(); b.B_core = Bc_use.copy(); b.T = T_use
        m.c = c_use.copy()
        t = t_start
        for _ in range(EXP_DUR):
            pl = deepcopy(frames[t])
            impose(pl, b, second_tag, b.cells(pcfg.width, pcfg.height, bcfg.footprint), pcfg, {})
            step_physical_body(b, pl, bcfg); step_internal_medium(m, b, mcfg); t += 1
        return b.B.copy(), om_vec(b, m), observer_J(deepcopy(frames[t_start]), 
            type('X', (), {'B': B_use, 'cells': body0.cells}) , bcfg)[0] if False else None

    t_pre2 = EXP_DUR + gap
    # build bodies at pre2
    b_ab = deepcopy(body0); m_ab = deepcopy(medium0); t = 0
    doses_tmp = {}
    for phase, tag in [( 'first', tags[0])] * EXP_DUR:
        pass
    # simpler path using ticks
    # Initial J after swap B: AB body gets BA's B
    pl0 = deepcopy(frames[t_pre2])
    # impose second tags on copies
    b_tmp = deepcopy(body0)
    b_tmp.B = B_pre2_BA.copy()  # swapped
    cells = b_tmp.cells(pcfg.width, pcfg.height, bcfg.footprint)
    impose(pl0, b_tmp, tags[1], cells, pcfg, {})  # AB's second tag MAT1
    J_swap_AB, _ = observer_J(pl0, b_tmp, bcfg)

    pl1 = deepcopy(frames[t_pre2])
    b_tmp2 = deepcopy(body0)
    b_tmp2.B = B_pre2_AB.copy()
    cells = b_tmp2.cells(pcfg.width, pcfg.height, bcfg.footprint)
    impose(pl1, b_tmp2, tags_BA[1], cells, pcfg, {})  # BA's second = MAT0
    J_swap_BA, _ = observer_J(pl1, b_tmp2, bcfg)
    # natural initial J
    J_nat_AB = sec_AB[0]['J']; J_nat_BA = sec_BA[0]['J']
    # Does swapping B swap the flux asymmetry relative to natural?
    # Compare J_swap_AB (MAT1 on BA's B) vs natural J_BA when BA does MAT0 — different tags.
    # Cleaner test: same second tag MAT1 on both B_pre2_AB and B_pre2_BA
    plA = deepcopy(frames[t_pre2]); plB = deepcopy(frames[t_pre2])
    bA = deepcopy(body0); bA.B = B_pre2_AB.copy()
    bB = deepcopy(body0); bB.B = B_pre2_BA.copy()
    impose(plA, bA, 'MAT1', bA.cells(pcfg.width,pcfg.height,bcfg.footprint), pcfg, {})
    impose(plB, bB, 'MAT1', bB.cells(pcfg.width,pcfg.height,bcfg.footprint), pcfg, {})
    J_MAT1_on_AB = observer_J(plA, bA, bcfg)[0]
    J_MAT1_on_BA = observer_J(plB, bB, bcfg)[0]
    dJ_same_tag = J_MAT1_on_AB - J_MAT1_on_BA
    # After B swap (AB gets BA's B), J_MAT1 should equal natural J_MAT1_on_BA
    bS = deepcopy(body0); bS.B = B_pre2_BA.copy()
    plS = deepcopy(frames[t_pre2])
    impose(plS, bS, 'MAT1', bS.cells(pcfg.width,pcfg.height,bcfg.footprint), pcfg, {})
    J_after_swap = observer_J(plS, bS, bcfg)[0]
    B_swap_follows = float(np.linalg.norm(J_after_swap - J_MAT1_on_BA)) < 1e-12

    # full state sufficiency
    fut_frames_start = EXP_DUR * 2 + gap
    def future_from(body, medium, t0):
        b = deepcopy(body); m = deepcopy(medium)
        for i in range(FUT):
            pl = deepcopy(frames[t0 + i])
            step_physical_body(b, pl, bcfg); step_internal_medium(m, b, mcfg)
        return om_vec(b, m)
    fut_AB = future_from(end_AB['body'], end_AB['medium'], end_AB['t'])
    fut_BA = future_from(end_BA['body'], end_BA['medium'], end_BA['t'])
    fut_div = float(np.linalg.norm(fut_AB - fut_BA))
    # match_self
    fut_AB2 = future_from(end_AB['body'], end_AB['medium'], end_AB['t'])
    match_self = float(np.linalg.norm(fut_AB - fut_AB2))
    # matched full state: BA future from AB end state
    fut_BA_from_AB = future_from(end_AB['body'], end_AB['medium'], end_BA['t'])
    # same t index — frames identical by construction for same absolute tick
    matched_div = float(np.linalg.norm(fut_AB - fut_BA_from_AB))

    # clips during gap/second?
    any_clip = any(x.get('clip_mat') for x in ticks_AB + ticks_BA)

    # total D_recv
    def sumJ(ticks, phase=None):
        s = np.zeros(3)
        for x in ticks:
            if phase is None or x['phase'] == phase:
                s += x['J']
        return s
    dRecv = sumJ(ticks_AB) - sumJ(ticks_BA)

    # EXP-3 style frac
    dJ_total = dRecv
    frac = float(np.linalg.norm(dJ_total) / Om0_B) if Om0_B > NUM_FLOOR else float('nan')

    # sequential full ΔB from per-tick actual
    dB_from_actual = np.zeros(3)
    for a, b in zip(ticks_AB, ticks_BA):
        dB_from_actual += a['dB_actual'] - b['dB_actual']
    # should equal dB_final
    actual_path_err = float(np.linalg.norm(dB_from_actual - dB_final))

    return {
        'seed': seed, 'gap': gap,
        'dose_AB': end_AB['doses'], 'dose_BA': end_BA['doses'],
        'dose_ok': all(abs(end_AB['doses'][k] - end_BA['doses'][k]) < 1e-9 for k in end_AB['doses']),
        'Om0': Om0, 'Om0_B': Om0_B, 'phys_ref': phys_ref,
        'above_phys': Om0 > phys_ref,
        'det_dup': det_dup,
        'dB_post1_vec': dB_post1.tolist(), 'dB_post1': n_post1,
        'dB_pre2_vec': dB_pre2.tolist(), 'dB_pre2': n_pre2,
        'cos_theta': cos_th,
        'w_post1': w_post, 'w_pre2': w_pre,
        'gap_ops_dB': {k: v.tolist() for k, v in gap_ops.items()},
        'gap_ops_norms': {k: float(np.linalg.norm(v)) for k, v in gap_ops.items()},
        'gap_traj': gap_traj,
        'dJ0_vec': dJ0.tolist(), 'dJ0': n_dJ0,
        'pred_dJ_vec': pred_dJ.tolist(), 'pred_err': pred_err,
        'Mw_equal': Mw_equal,
        'Mw_AB': Mw_AB.tolist(), 'Mw_BA': Mw_BA.tolist(),
        'dRecv2_vec': dRecv2.tolist(), 'dRecv2': n_dRecv2,
        'dRecv_vec': dRecv.tolist(), 'dRecv': float(np.linalg.norm(dRecv)),
        'flux_traj': flux_traj,
        'op_phase': {ph: {k: v.tolist() for k, v in ops.items()} for ph, ops in op_phase.items()},
        'op_phase_norms': {ph: {k: float(np.linalg.norm(v)) for k, v in ops.items()} for ph, ops in op_phase.items()},
        'dB_final': dB_final.tolist(),
        'recon_dB': recon_dB.tolist(),
        'R_full': R_full.tolist(), 'R_full_norm': float(np.linalg.norm(R_full)),
        'max_recon_err': float(max_recon_err),
        'actual_path_err': actual_path_err,
        'proj_post1': proj_post1, 'proj_pre2': proj_pre2,
        'sus_post1': sus_post1, 'sus_pre2': sus_pre2,
        'gap_replay_err': gap_replay_err,
        'B_swap_follows': B_swap_follows,
        'dJ_same_tag_MAT1': dJ_same_tag.tolist(),
        'fut_div': fut_div, 'match_self': match_self, 'matched_div': matched_div,
        'any_clip': any_clip,
        'frac_dJ_over_OmB': frac,
        'permeability': p.tolist(),
    }


def main():
    RESULTS = {'contig': {}, 'spaced': {}}
    for seed in SEEDS:
        RESULTS['contig'][seed] = analyze_pair(seed, GAP_CONTIG)
        RESULTS['spaced'][seed] = analyze_pair(seed, GAP_SPACED)
        print('seed', seed,
              'contig Om0', RESULTS['contig'][seed]['Om0'],
              'spaced Om0', RESULTS['spaced'][seed]['Om0'],
              'cos', RESULTS['spaced'][seed]['cos_theta'],
              'dB_post1', RESULTS['spaced'][seed]['dB_post1'],
              'dB_pre2', RESULTS['spaced'][seed]['dB_pre2'],
              'dJ0', RESULTS['spaced'][seed]['dJ0'],
              'dRecv2', RESULTS['spaced'][seed]['dRecv2'],
              'R_full', RESULTS['spaced'][seed]['R_full_norm'],
              'max_recon', RESULTS['spaced'][seed]['max_recon_err'])

    # primary seed 23 comparisons
    c = RESULTS['contig'][23]
    s = RESULTS['spaced'][23]

    summary = {
        'freeze_ok': FREEZE_OK,
        'FREEZE': FREEZE,
        'SEEDS': SEEDS,
        'EXP_DUR': EXP_DUR,
        'GAP_CONTIG': GAP_CONTIG,
        'GAP_SPACED': GAP_SPACED,
        'MAT_AMP': MAT_AMP,
        'NUM_FLOOR': NUM_FLOOR,
        'PHYS_FRAC': PHYS_FRAC,
        'ACCT_TOL': ACCT_TOL,
        'RESULTS': RESULTS,
        'compare_23': {
            'Om0_c': c['Om0'], 'Om0_s': s['Om0'],
            'dB_post1_c': c['dB_post1'], 'dB_post1_s': s['dB_post1'],
            'dB_pre2_c': c['dB_pre2'], 'dB_pre2_s': s['dB_pre2'],
            'dJ0_c': c['dJ0'], 'dJ0_s': s['dJ0'],
            'dRecv2_c': c['dRecv2'], 'dRecv2_s': s['dRecv2'],
            'cos_s': s['cos_theta'],
            'sus_post1_s': s['sus_post1'], 'sus_pre2_s': s['sus_pre2'],
            'proj_post1_s': s['proj_post1'], 'proj_pre2_s': s['proj_pre2'],
            'gap_ops_s': s['gap_ops_norms'],
            'R_full_s': s['R_full_norm'],
            'max_recon_s': s['max_recon_err'],
            'frac_s': s['frac_dJ_over_OmB'],
        },
    }
    # numpy-safe json
    def conv(o):
        if isinstance(o, dict):
            return {str(k): conv(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [conv(x) for x in o]
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, (np.bool_,)):
            return bool(o)
        return o
    (ROOT / 'experiment_summary.json').write_text(json.dumps(conv(summary), indent=2))
    print('WROTE', ROOT / 'experiment_summary.json')
    print('compare_23', json.dumps(summary['compare_23'], indent=2))

if __name__ == '__main__':
    main()
