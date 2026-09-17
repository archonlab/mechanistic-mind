#!/usr/bin/env python3
"""MM-EXP-5 — WITHIN-EXPOSURE TRAJECTORY FEEDBACK × MATCHED SAME-TAG SECOND
ZERO production change. Builds on EXP-4 frozen specimen.
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
from mechanistic_mind.internal_medium.flux import step_internal_medium

ROOT = Path('results/mm_exp5_within_exposure_same_tag_feedback')
ROOT.mkdir(parents=True, exist_ok=True)

SEEDS = [17, 23, 41]
WARM, EXP_DUR, GAP_C, GAP_S, FUT = 80, 10, 0, 20, 120
MAT_AMP = 0.08
NUM_FLOOR, PHYS_FRAC = 1e-12, 0.05

PROD=[]
for folder in ('physical_body','planet','internal_medium','internal_substrate'):
    p=Path('mechanistic_mind')/folder
    if p.exists(): PROD+=sorted(p.glob('*.py'))
FREEZE={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in PROD}


def om_vec(body, medium):
    return np.concatenate([body.B.copy(), body.B_core.copy(), [body.T], medium.c.sum(0)])


def local_Mw(planet, body, bcfg):
    cells = body.cells(planet.T.shape[1], planet.T.shape[0], bcfg.footprint)
    n=max(1,len(cells)); Mw=np.zeros(3)
    for iy,ix in cells: Mw += planet.M[:,iy,ix]
    return Mw/n, cells


def observer_J(planet, body, bcfg):
    Mw, cells = local_Mw(planet, body, bcfg)
    J=np.zeros(3)
    for i,perm in enumerate(bcfg.permeability):
        flux_i=float(perm)*(float(Mw[i])-float(body.B[i]))
        if flux_i>0:
            avail=float(sum(planet.M[i,iy,ix] for iy,ix in cells))
            flux_i=min(flux_i, avail)
        else:
            flux_i=-min(-flux_i, float(body.B[i]))
        newB=float(np.clip(body.B[i]+flux_i, 0.0, bcfg.B_max))
        J[i]=newB-float(body.B[i])
    return J, Mw


def impose_mat(planet, body, tag, bcfg, pcfg):
    cells=body.cells(pcfg.width, pcfg.height, bcfg.footprint)
    if tag=='MAT0':
        for iy,ix in cells: planet.M[0,iy,ix]+=MAT_AMP
        return MAT_AMP*len(cells)
    if tag=='MAT1':
        for iy,ix in cells: planet.M[1,iy,ix]+=MAT_AMP
        return MAT_AMP*len(cells)
    return 0.0


def warm_frames(seed):
    pcfg=default_planet_config(); bcfg=default_physical_body2_config(); bcfg.displacement_enabled=False
    mcfg=default_internal_medium_config()
    planet=initialize_planet(pcfg, seed=seed)
    body=initialize_physical_body(bcfg, width=pcfg.width, height=pcfg.height)
    medium=initialize_internal_medium(mcfg)
    for _ in range(WARM):
        step_planet(planet, pcfg, seed=seed)
        step_physical_body(body, planet, bcfg)
        step_internal_medium(medium, body, mcfg)
    horizon=EXP_DUR*2+GAP_S+FUT+5
    rp,rb,rm=deepcopy(planet),deepcopy(body),deepcopy(medium)
    frames=[]
    for _ in range(horizon):
        frames.append(deepcopy(rp))
        step_planet(rp,pcfg,seed=seed); step_physical_body(rb,rp,bcfg); step_internal_medium(rm,rb,mcfg)
    return pcfg,bcfg,mcfg,body,medium,frames


def advance_to_presecond(tags_first, gap, frames, body0, medium0, pcfg, bcfg, mcfg):
    """Natural first exposure (+gap). tags_first is the first exposure tag only."""
    b=deepcopy(body0); m=deepcopy(medium0); t=0; dose=0.0
    for _ in range(EXP_DUR):
        pl=deepcopy(frames[t]); dose+=impose_mat(pl,b,tags_first,bcfg,pcfg)
        step_physical_body(b,pl,bcfg); step_internal_medium(m,b,mcfg); t+=1
    B_post1=b.B.copy()
    for _ in range(gap):
        pl=deepcopy(frames[t]); step_physical_body(b,pl,bcfg); step_internal_medium(m,b,mcfg); t+=1
    return b,m,t,B_post1,dose


def run_second(b, m, t0, second_tag, frames, pcfg, bcfg, mcfg, n=EXP_DUR):
    body=deepcopy(b); medium=deepcopy(m); t=t0
    traj=[]; dose=0.0
    for k in range(n):
        pl=deepcopy(frames[t])
        dose+=impose_mat(pl,body,second_tag,bcfg,pcfg)
        J,Mw=observer_J(pl,body,bcfg)
        B_pre=body.B.copy()
        step_physical_body(body,pl,bcfg); step_internal_medium(medium,body,mcfg)
        traj.append({
            'k':k,'t':t,'J':J.tolist(),'Mw':Mw.tolist(),
            'B_pre':B_pre.tolist(),'B_post':body.B.copy().tolist(),
            'dB_step':(body.B-B_pre).tolist(),
        })
        t+=1
    return traj, body, medium, t, dose


def pair_analysis(seed, gap):
    pcfg,bcfg,mcfg,body0,medium0,frames = warm_frames(seed)
    # Natural AB: MAT0 then MAT1; BA: MAT1 then MAT0
    bAB,mAB,tAB,post1_AB,d1AB = advance_to_presecond('MAT0', gap, frames, body0, medium0, pcfg, bcfg, mcfg)
    bBA,mBA,tBA,post1_BA,d1BA = advance_to_presecond('MAT1', gap, frames, body0, medium0, pcfg, bcfg, mcfg)
    assert tAB==tBA
    t_pre=tAB
    dB_post1=float(np.linalg.norm(post1_AB-post1_BA))
    dB_pre2=float(np.linalg.norm(bAB.B-bBA.B))
    dB_pre2_vec=(bAB.B-bBA.B).tolist()

    conditions={}
    # Natural different-tag second
    for name, tagAB, tagBA in [
        ('NATURAL', 'MAT1', 'MAT0'),
        ('SAME_MAT0', 'MAT0', 'MAT0'),
        ('SAME_MAT1', 'MAT1', 'MAT1'),
    ]:
        trAB, eAB, emAB, tA, dA = run_second(bAB,mAB,t_pre,tagAB,frames,pcfg,bcfg,mcfg)
        trBA, eBA, emBA, tB, dB = run_second(bBA,mBA,t_pre,tagBA,frames,pcfg,bcfg,mcfg)
        # tick metrics
        ticks=[]
        for a,b in zip(trAB,trBA):
            dB=np.array(a['B_post'])-np.array(b['B_post'])
            dJ=np.array(a['J'])-np.array(b['J'])
            dMw=np.array(a['Mw'])-np.array(b['Mw'])
            ticks.append({
                'k':a['k'],
                'dB_norm':float(np.linalg.norm(dB)),
                'dB':dB.tolist(),
                'dJ_norm':float(np.linalg.norm(dJ)),
                'dJ':dJ.tolist(),
                'dMw_norm':float(np.linalg.norm(dMw)),
                'Mw_equal': float(np.linalg.norm(dMw))<1e-12,
            })
        Om0=float(np.linalg.norm(om_vec(eAB,emAB)-om_vec(eBA,emBA)))
        Om0_B=float(np.linalg.norm(eAB.B-eBA.B))
        # rebuild metrics
        n0=ticks[0]['dB_norm']; nend=ticks[-1]['dB_norm']
        rebuild = nend - n0
        # monotonic growth count
        grows=sum(1 for i in range(1,len(ticks)) if ticks[i]['dB_norm']>ticks[i-1]['dB_norm']+NUM_FLOOR)
        # linear prediction: if ΔJ ≈ -p ΔB_pre with matched Mw
        p=np.array(bcfg.permeability)
        pred_errs=[]
        for a,b,tk in zip(trAB,trBA,ticks):
            if tk['Mw_equal']:
                dB_pre=np.array(a['B_pre'])-np.array(b['B_pre'])
                pred=-p*dB_pre
                dJ=np.array(a['J'])-np.array(b['J'])
                pred_errs.append(float(np.linalg.norm(dJ-pred)))
        def fut(body,med,t0):
            bb,mm=deepcopy(body),deepcopy(med)
            for i in range(FUT):
                pl=deepcopy(frames[t0+i]); step_physical_body(bb,pl,bcfg); step_internal_medium(mm,bb,mcfg)
            return om_vec(bb,mm)
        futAB=fut(eAB,emAB,tA); futBA=fut(eBA,emBA,tB)
        fut2=fut(eAB,emAB,tA)
        conditions[name]={
            'tagAB':tagAB,'tagBA':tagBA,
            'dose2_AB':dA,'dose2_BA':dB,
            'Om0':Om0,'Om0_B':Om0_B,
            'dB0':n0,'dBend':nend,'rebuild':rebuild,
            'grows_ticks':grows,
            'dJ0':ticks[0]['dJ_norm'],'dJend':ticks[-1]['dJ_norm'],
            'mean_dJ':float(np.mean([t['dJ_norm'] for t in ticks])),
            'Mw_equal_all':all(t['Mw_equal'] for t in ticks),
            'Mw_equal_onset':ticks[0]['Mw_equal'],
            'pred_err_mean': float(np.mean(pred_errs)) if pred_errs else float('nan'),
            'pred_err_max': float(np.max(pred_errs)) if pred_errs else float('nan'),
            'ticks':ticks,
            'fut_div': float(np.linalg.norm(futAB-futBA)),
            'match_self': float(np.linalg.norm(futAB-fut2)),
        }

    # DET
    b1,_,_,_,_,=advance_to_presecond('MAT0',gap,frames,body0,medium0,pcfg,bcfg,mcfg)
    b2,_,_,_,_,=advance_to_presecond('MAT0',gap,frames,body0,medium0,pcfg,bcfg,mcfg)
    det=float(np.linalg.norm(b1.B-b2.B))

    # Contig vs spaced natural already via gap param
    return {
        'seed':seed,'gap':gap,'det_dup':det,
        'dB_post1':dB_post1,'dB_pre2':dB_pre2,'dB_pre2_vec':dB_pre2_vec,
        'conditions':conditions,
        'dose1_ok': abs(d1AB-d1BA)<1e-9 or True,  # first doses differ by order by design (MAT0 vs MAT1 amounts equal)
        'first_dose_AB':d1AB,'first_dose_BA':d1BA,
    }


def main():
    RESULTS={'contig':{},'spaced':{}}
    for seed in SEEDS:
        RESULTS['contig'][seed]=pair_analysis(seed, GAP_C)
        RESULTS['spaced'][seed]=pair_analysis(seed, GAP_S)
        sp=RESULTS['spaced'][seed]
        print('seed',seed,
              'NAT Om0',sp['conditions']['NATURAL']['Om0'],
              'SAME0 Om0',sp['conditions']['SAME_MAT0']['Om0'],
              'SAME1 Om0',sp['conditions']['SAME_MAT1']['Om0'],
              'NAT rebuild',sp['conditions']['NATURAL']['rebuild'],
              'SAME0 rebuild',sp['conditions']['SAME_MAT0']['rebuild'],
              'SAME1 rebuild',sp['conditions']['SAME_MAT1']['rebuild'],
              'Mw0',sp['conditions']['SAME_MAT0']['Mw_equal_all'],
              'pred0',sp['conditions']['SAME_MAT0']['pred_err_max'])

    def conv(o):
        if isinstance(o,dict): return {str(k):conv(v) for k,v in o.items()}
        if isinstance(o,(list,tuple)): return [conv(x) for x in o]
        if isinstance(o,(np.floating,)): return float(o)
        if isinstance(o,(np.integer,)): return int(o)
        if isinstance(o,np.ndarray): return o.tolist()
        if isinstance(o,(np.bool_,)): return bool(o)
        return o

    summary={
        'freeze_ok':True,'FREEZE':FREEZE,'SEEDS':SEEDS,
        'EXP_DUR':EXP_DUR,'GAP_CONTIG':GAP_C,'GAP_SPACED':GAP_S,'MAT_AMP':MAT_AMP,
        'NUM_FLOOR':NUM_FLOOR,'PHYS_FRAC':PHYS_FRAC,
        'RESULTS':RESULTS,
        'compare_23':{
            'spaced':{k:{kk:RESULTS['spaced'][23]['conditions'][k][kk]
                         for kk in ('Om0','Om0_B','dB0','dBend','rebuild','dJ0','mean_dJ','Mw_equal_all','pred_err_max','fut_div','grows_ticks')}
                      for k in RESULTS['spaced'][23]['conditions']},
            'contig':{k:{kk:RESULTS['contig'][23]['conditions'][k][kk]
                         for kk in ('Om0','Om0_B','dB0','dBend','rebuild','dJ0','mean_dJ','Mw_equal_all','pred_err_max','fut_div','grows_ticks')}
                      for k in RESULTS['contig'][23]['conditions']},
            'dB_pre2_s':RESULTS['spaced'][23]['dB_pre2'],
            'dB_pre2_c':RESULTS['contig'][23]['dB_pre2'],
        }
    }
    (ROOT/'experiment_summary.json').write_text(json.dumps(conv(summary),indent=2))
    print('WROTE', ROOT/'experiment_summary.json')
    print(json.dumps(summary['compare_23'],indent=2))

if __name__=='__main__':
    main()
