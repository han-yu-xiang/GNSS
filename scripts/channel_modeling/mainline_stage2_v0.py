"""Numerical SAGE-only V0 helpers. No signal, MAT, CIR or HDF5 access.

Path rows are conditional on the existing Stage2 selector. Scene IDs, not
windows or paths, define validation and resampling units.
"""
from __future__ import annotations

import warnings
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd
from scipy import optimize, stats

from mainline_stage2_model_prep import mpc_counts_by_selected_window, leave_one_scene_out_folds


VARIABLES = {
    'excess_delay_chips': ['gamma', 'lognormal', 'weibull'],
    'doppler_offset_hz': ['normal', 'laplace', 'student_t'],
    'relative_power_db': ['normal', 'laplace', 'student_t'],
}
DISTRIBUTIONS = dict(gamma=stats.gamma, lognormal=stats.lognorm,
                     weibull=stats.weibull_min, normal=stats.norm,
                     laplace=stats.laplace, student_t=stats.t)
POSITIVE = {'gamma', 'lognormal', 'weibull'}
TAGS = ['scene_id', 'prn', 'tracking_channel', 'environment_class']
KEY = ['run_id', 'window_id']
NUMERIC = ['delay_samples', 'excess_delay_samples', 'excess_delay_chips', 'excess_path_length_m',
           'doppler_hz', 'doppler_offset_hz', 'relative_power_db', 'recording_time_s']


def _window_frame(rows):
    frame = pd.DataFrame(rows).copy()
    if frame.duplicated(KEY).any():
        raise ValueError('duplicate overlay window identity')
    for value in frame.window_id:
        if not isinstance(value, str) or not value.isascii() or not value.isdecimal() or str(int(value)) != value or int(value) < 1:
            raise ValueError('overlay requires canonical window identity')
    return frame


def prepare_population(rows, cohort, geometry=None, trajectory=None):
    """Retain every path; enrich via one-to-one exact-window identities."""
    counts = mpc_counts_by_selected_window(rows)
    paths = pd.DataFrame(rows).copy()
    tasks = {task['run_id']: task for task in cohort['tasks']}
    if len(tasks) != len(cohort['tasks']) or set(paths.run_id) != set(tasks):
        raise ValueError('cohort run identity set mismatch')
    for run, group in paths.groupby('run_id', sort=False):
        task = tasks[run]
        for tag in TAGS + ['elevation_group']:
            if set(group[tag].astype(str)) != {str(task[tag])}:
                raise ValueError(f'cohort {tag} identity mismatch for {run}')
    for name in ['path_id','is_multipath','selected_L']:
        numeric = pd.to_numeric(paths[name], errors='raise')
        if not np.isfinite(numeric).all() or (numeric % 1 != 0).any():
            raise ValueError(name + ' must be finite integral values')
        paths[name] = numeric.astype(int)
    for _, group in paths.groupby(KEY, sort=False):
        if set(group.selected_L) != {len(group)}:
            raise ValueError('selected_L/path count mismatch')
    for col in NUMERIC:
        paths[col] = pd.to_numeric(paths[col], errors='coerce')
    windows = paths[paths.path_id == 1][KEY + TAGS + ['elevation_group','recording_time_s']].copy()
    windows['mpc_count'] = [counts[tuple(k)] for k in windows[KEY].itertuples(index=False, name=None)]

    def join_overlay(overlay, fields, geometry_join=False):
        nonlocal windows
        other = _window_frame(overlay)
        required = KEY + ['scene_id','prn','tracking_channel'] + (
            ['environment_class','frozen_elevation_group','elevation_source','elevation_value_deg','receiver_height_source']
            if geometry_join else ['position_status','position_source'])
        if set(required)-set(other.columns):
            raise ValueError('overlay schema missing identity/source fields')
        if set(other[KEY].itertuples(index=False,name=None)) != set(windows[KEY].itertuples(index=False,name=None)):
            raise ValueError('overlay window set mismatch')
        check_tags = [c for c in TAGS if c in other]
        expected = windows.set_index(KEY)
        for _, row in other.iterrows():
            base = expected.loc[(row.run_id,row.window_id)]
            if any(str(row[c]) != str(base[c]) for c in check_tags):
                raise ValueError('overlay identity label mismatch')
            if geometry_join and str(row.frozen_elevation_group) != str(base.elevation_group):
                raise ValueError('overlay frozen elevation identity mismatch')
        selected = [c for c in fields if c in other]
        windows = windows.merge(other[KEY + selected], on=KEY, how='left', validate='one_to_one', sort=False)

    if geometry is not None:
        join_overlay(geometry, ['elevation_value_deg','elevation_source','receiver_height_source',
                               'receiver_position_status'], True)
    else:
        windows['elevation_value_deg'] = ''
        windows['elevation_source'] = 'UNAVAILABLE'
        windows['receiver_height_source'] = ''
    if trajectory is not None:
        join_overlay(trajectory, ['position_status','position_source','route_component_id',
                                 'route_cumulative_distance_m','receiver_speed_mps'])
    else:
        windows['position_status'] = 'UNAVAILABLE'
        windows['position_source'] = 'UNAVAILABLE'
    windows['elevation_deg'] = pd.to_numeric(windows.elevation_value_deg,errors='coerce')
    available = windows.elevation_source.isin(['GSV_MEASURED','EPHEMERIS_DERIVED'])
    if ((~np.isfinite(windows.elevation_deg)) & available).any():
        raise ValueError('available elevation has invalid numeric value')
    measured = windows.elevation_source == 'GSV_MEASURED'
    if ((windows.elevation_deg.lt(0)|windows.elevation_deg.gt(90)) & measured).any():
        raise ValueError('measured elevation outside [0,90]')
    if (np.isfinite(windows.elevation_deg) & ~available).any():
        raise ValueError('missing elevation contains a numeric value')
    derived = windows.elevation_source == 'EPHEMERIS_DERIVED'
    if (~windows.loc[derived,'receiver_height_source'].isin(['GGA_ELLIPSOIDAL_HEIGHT','ZERO_HEIGHT_ASSUMPTION'])).any():
        raise ValueError('derived elevation height source is missing or invalid')
    windows['geometry_stratum'] = windows.elevation_source
    windows.loc[derived,'geometry_stratum'] = 'EPHEMERIS_DERIVED_' + windows.loc[derived,'receiver_height_source']
    windows['numeric_elevation_band'] = windows.elevation_deg.map(elevation_band)
    enrichment = [c for c in windows if c not in paths and c not in TAGS]
    paths = paths.merge(windows[KEY+enrichment],on=KEY,how='left',validate='many_to_one',sort=False)
    audit = dict(path_n=len(paths),direct_n=int((paths.is_multipath==0).sum()),
                 mpc_n=int(paths.is_multipath.sum()),selected_window_n=len(windows),
                 run_count=paths.run_id.nunique(),scene_count=paths.scene_id.nunique(),
                 window_elevation_source_counts=dict(Counter(windows.elevation_source)),
                 window_height_source_counts=dict(Counter(windows.loc[derived,'receiver_height_source'])),
                 position_matched_n=int((windows.position_status=='POSITION_MATCHED').sum()),
                 joint_elevation_position_n=int((available & (windows.position_status=='POSITION_MATCHED')).sum()))
    return paths,windows,audit


def elevation_band(value):
    if not np.isfinite(value): return 'MISSING'
    if value < 0 or value > 90: return 'OUT_OF_FORMAL_RANGE'
    return 'Low' if value < 30 else 'Mid' if value < 60 else 'High'


def height_source_support(geometry_rows):
    """Count source observations without exposing source paths/IDs or heights."""
    derived=[r for r in geometry_rows if r['elevation_source']=='EPHEMERIS_DERIVED']
    result=[]
    collections=[('GLOBAL','ALL',derived)]
    for scene in sorted({r['scene_id'] for r in derived}):
        collections.append(('scene_id',scene,[r for r in derived if r['scene_id']==scene]))
    for scope,scene,rows in collections:
        for source in ['GGA_ELLIPSOIDAL_HEIGHT','ZERO_HEIGHT_ASSUMPTION']:
            subset=[r for r in rows if r['receiver_height_source']==source]
            identities=set()
            if source=='GGA_ELLIPSOIDAL_HEIGHT':
                for row in subset:
                    if not row.get('receiver_height_source_file') or not row.get('receiver_height_record_id'):
                        raise ValueError('GGA height source identity missing')
                    identities.add((row['scene_id'],row['receiver_height_source_file'],row['receiver_height_record_id']))
            result.append(dict(scope=scope,scene_id=scene,receiver_height_source=source,
                derived_window_n=len(subset),distinct_height_record_n=len(identities)))
    return result


def quality_summary(values):
    original = list(values)
    missing = [v is None or str(v).strip()=='' for v in original]
    invalid, numbers = 0, []
    for value, absent in zip(original,missing):
        if absent:continue
        try:numbers.append(float(value))
        except (TypeError,ValueError):invalid+=1
    all_numeric = np.asarray(numbers,dtype=float)
    finite = all_numeric[np.isfinite(all_numeric)]
    result = dict(total_n=len(original),missing_n=sum(missing),invalid_text_n=invalid,
                  nonfinite_n=int((~np.isfinite(all_numeric)).sum()),finite_n=len(finite),
                  zero_n=int((finite==0).sum()),negative_n=int((finite<0).sum()),
                  positive_n=int((finite>0).sum()))
    fields = ['mean','std','median','iqr','min','max','p5','p25','p50','p75','p95','p99','tukey_outlier_n']
    result.update(dict.fromkeys(fields))
    if len(finite):
        q = np.quantile(finite,[.05,.25,.5,.75,.95,.99])
        result.update(dict(zip(['p5','p25','p50','p75','p95','p99'],q.tolist())))
        iqr = q[3]-q[1]
        result.update(mean=float(finite.mean()),std=float(finite.std(ddof=1)) if len(finite)>1 else None,
            median=float(q[2]),iqr=float(iqr),min=float(finite.min()),max=float(finite.max()),
            tukey_outlier_n=int(((finite<q[1]-1.5*iqr)|(finite>q[3]+1.5*iqr)).sum()))
    return result


def fit_distribution(values, family):
    values = np.asarray(values,dtype=float)
    finite = values[np.isfinite(values)]
    data = finite[finite>0] if family in POSITIVE else finite
    result = dict(family=family,status='FAILED',n=len(data),input_n=len(values),
                  excluded_nonfinite_n=len(values)-len(finite),
                  excluded_nonpositive_n=len(finite)-len(data),parameters=[],
                  support='x > 0; loc fixed 0' if family in POSITIVE else 'all finite real x',
                  loglik=None,aicc=None,bic=None,optimizer_status=None,converged=None,
                  warnings=[],failure_reason='')
    if len(data)<4 or np.ptp(data)==0:
        result['failure_reason']='INSUFFICIENT_OR_CONSTANT_DATA';return result
    dist = DISTRIBUTIONS[family]
    optimizer_records=[]
    def optimizer(func,x0,args=(),disp=0):
        opt = optimize.fmin(func,x0,args=args,full_output=True,disp=False,
                            maxiter=10000,maxfun=20000,xtol=1e-8,ftol=1e-8)
        optimizer_records.append(dict(warnflag=int(opt[4]),iterations=int(opt[2]),function_calls=int(opt[3])))
        return opt[0]
    try:
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter('always')
            params = dist.fit(data,floc=0,optimizer=optimizer) if family in POSITIVE else dist.fit(data,optimizer=optimizer)
        result['warnings']=[str(w.message) for w in seen]
        result['parameters']=list(map(float,params))
        result['optimizer_status'] = optimizer_records or 'SCIPY_ANALYTIC_OR_INTERNAL_SOLVER; no optimizer flag exposed'
        result['converged'] = all(r['warnflag']==0 for r in optimizer_records) if optimizer_records else None
        ll=float(np.sum(dist.logpdf(data,*params)))
        if not np.all(np.isfinite(params)) or params[-1]<=0 or not np.isfinite(ll):
            raise ValueError('nonfinite parameters/loglikelihood or nonpositive scale')
        if result['converged'] is False:raise ValueError('MLE optimizer did not converge')
        k=2 if family in POSITIVE or family in ['normal','laplace'] else 3
        n=len(data);aic=2*k-2*ll
        result.update(status='PASS',loglik=ll,parameter_k=k,aicc=aic+2*k*(k+1)/(n-k-1) if n>k+1 else None,
                      bic=k*np.log(n)-2*ll,observed_min=float(data.min()),observed_max=float(data.max()))
    except (ValueError,RuntimeError,FloatingPointError,OverflowError) as exc:
        result['failure_reason']=f'{type(exc).__name__}: {exc}'
    return result


def score_fit(fit,values):
    values=np.asarray(values,dtype=float);data=values[np.isfinite(values)]
    result=dict(test_n=len(values),finite_test_n=len(data),missing_nonfinite_test_n=len(values)-len(data),
                support_violation_n=int((data<=0).sum()) if fit['family'] in POSITIVE else 0,
                mean_loglik=None,positive_support_mean_loglik=None)
    if fit['status']!='PASS' or not len(data):return result
    scores=DISTRIBUTIONS[fit['family']].logpdf(data,*fit['parameters'])
    result['mean_loglik']=float(np.mean(scores)) if np.all(np.isfinite(scores)) else '-Infinity'
    supported=data[data>0] if fit['family'] in POSITIVE else data
    if len(supported):result['positive_support_mean_loglik']=float(np.mean(DISTRIBUTIONS[fit['family']].logpdf(supported,*fit['parameters'])))
    return result


def evaluate_loso(mpc,variables=None,scopes=None):
    variables=variables or VARIABLES;scopes=scopes or ['GLOBAL','ENV:Urban']
    scores,manifest=[],[]
    for scope in scopes:
        group=mpc if scope=='GLOBAL' else mpc[mpc.environment_class==scope.removeprefix('ENV:')]
        if group.scene_id.nunique()<2:continue
        group=group.reset_index(drop=True)
        for fold in leave_one_scene_out_folds(group.to_dict('records')):
            train=group.iloc[fold['train_indices']];test=group.iloc[fold['test_indices']]
            scenes=sorted(train.scene_id.unique());held=fold['held_out_scene_id']
            manifest.append(dict(scope=scope,held_out_scene_id=held,training_scene_ids=scenes,
                train_n=len(train),test_n=len(test),test_run_ids=sorted(test.run_id.unique()),
                scene_overlap_n=len(set(train.scene_id)&set(test.scene_id))))
            for variable,families in variables.items():
                for family in families:
                    fit=fit_distribution(train[variable],family) if len(scenes)>=2 else dict(
                        status='INSUFFICIENT_SUPPORT',family=family,parameters=[],failure_reason='fewer than two training scenes')
                    scores.append(dict(scope=scope,held_out_scene_id=held,variable=variable,family=family,
                        train_scene_n=len(scenes),train_n=len(train),fit_status=fit['status'],
                        fit_parameters=fit['parameters'],failure_reason=fit['failure_reason'],
                        **score_fit(fit,test[variable])))
    return scores,manifest


def summarize_scores(scores):
    groups={}
    for row in scores:groups.setdefault((row['scope'],row['variable'],row['family']),[]).append(row)
    result=[]
    for (scope,variable,family),rows in groups.items():
        usable=[r for r in rows if r['fit_status']=='PASS' and r['mean_loglik'] is not None]
        finite=[r for r in usable if isinstance(r['mean_loglik'],(float,int))]
        macro = float(np.mean([r['mean_loglik'] for r in finite])) if finite else None
        if len(finite)<len(usable):macro='-Infinity'
        result.append(dict(scope=scope,variable=variable,family=family,fold_n=len(rows),
            evaluated_fold_n=len(usable),finite_score_fold_n=len(finite),macro_mean_loglik=macro,
            macro_std_across_scenes=float(np.std([r['mean_loglik'] for r in finite],ddof=1)) if len(finite)>1 else None,
            support_violation_n=sum(r['support_violation_n'] for r in usable),
            failed_or_unsupported_fold_n=len(rows)-len(usable)))
    return result


def paired_environment_comparison(scores):
    """Compare environment and global fits on identical held-out scenes only."""
    global_rows={(r['held_out_scene_id'],r['variable'],r['family']):r for r in scores if r['scope']=='GLOBAL'}
    pairs=[]
    for row in scores:
        if not row['scope'].startswith('ENV:'):continue
        base=global_rows.get((row['held_out_scene_id'],row['variable'],row['family']))
        if base is None:continue
        if row['finite_test_n']!=base['finite_test_n']:raise ValueError('paired test population mismatch')
        usable=(row['fit_status']==base['fit_status']=='PASS' and
                isinstance(row['mean_loglik'],(int,float)) and isinstance(base['mean_loglik'],(int,float)))
        pairs.append(dict(scope=row['scope'],held_out_scene_id=row['held_out_scene_id'],
            variable=row['variable'],family=row['family'],finite_test_n=row['finite_test_n'],
            status='EVALUATED' if usable else 'NOT_EVALUABLE',
            delta_env_minus_global=row['mean_loglik']-base['mean_loglik'] if usable else None))
    grouped={}
    for row in pairs:grouped.setdefault((row['scope'],row['variable'],row['family']),[]).append(row)
    summary=[]
    for (scope,variable,family),rows in grouped.items():
        delta=[r['delta_env_minus_global'] for r in rows if r['status']=='EVALUATED']
        summary.append(dict(scope=scope,variable=variable,family=family,paired_scene_n=len(delta),
            macro_delta_env_minus_global=float(np.mean(delta)) if delta else None,
            improved_scene_n=sum(d>0 for d in delta),status='EXPLORATORY' if len(delta)>=3 else 'INSUFFICIENT_SUPPORT'))
    return pairs,summary


def relation_summary(frame):
    x=frame.excess_delay_chips.to_numpy(float);y=frame.relative_power_db.to_numpy(float)
    mask=np.isfinite(x)&np.isfinite(y);x=x[mask];y=y[mask]
    result=dict(n=len(x),slope_db_per_chip=None,intercept_db=None,spearman_rho=None,r_squared=None)
    if len(x)<3 or np.ptp(x)==0 or np.ptp(y)==0:return result
    regression=stats.linregress(x,y)
    result.update(slope_db_per_chip=float(regression.slope),intercept_db=float(regression.intercept),
                  spearman_rho=float(stats.spearmanr(x,y).statistic),r_squared=float(regression.rvalue**2))
    return result


def scene_bootstrap_relation(frame,iterations=1000,seed=20261024):
    result=relation_summary(frame)
    result.update(scene_n=frame.scene_id.nunique(),bootstrap_unit='whole_scene_with_multiplicity',
                  bootstrap_iterations=iterations,bootstrap_seed=seed)
    groups=[g for _,g in frame.groupby('scene_id',sort=True)]
    draws=[];rng=np.random.default_rng(seed)
    if len(groups)>=3:
        for _ in range(iterations):
            chosen=rng.integers(0,len(groups),size=len(groups))
            draw=relation_summary(pd.concat([groups[i] for i in chosen],ignore_index=True))
            if draw['slope_db_per_chip'] is not None:draws.append(draw)
    for metric,label in [('slope_db_per_chip','slope'),('intercept_db','intercept'),('spearman_rho','rho')]:
        bounds=np.quantile([d[metric] for d in draws],[.025,.975]).tolist() if draws else [None,None]
        result[label+'_ci_low'],result[label+'_ci_high']=bounds
    result['valid_bootstrap_draw_n']=len(draws)
    return result


def correlation_rows(frame,scope):
    result=[]
    for left,right in [('excess_delay_chips','doppler_offset_hz'),('excess_delay_chips','relative_power_db'),('doppler_offset_hz','relative_power_db')]:
        a=frame[left].to_numpy(float);b=frame[right].to_numpy(float);mask=np.isfinite(a)&np.isfinite(b)
        value=stats.spearmanr(a[mask],b[mask]).statistic if mask.sum()>2 and np.ptp(a[mask])>0 and np.ptp(b[mask])>0 else None
        result.append(dict(scope=scope,left=left,right=right,n=int(mask.sum()),scene_n=frame.scene_id.nunique(),
                           spearman_rho=float(value) if value is not None else None))
    return result
