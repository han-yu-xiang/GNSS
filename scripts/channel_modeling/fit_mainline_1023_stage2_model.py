#!/usr/bin/env python3
"""Run an exploratory, CSV-only Mainline SAGE Stage2 statistical V0.

Outputs are new-only. This command never invokes MATLAB, changes production,
reads signals, opens CIR/MAT/HDF5, or associates incomplete CIR features.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from scipy import stats

import mainline_stage2_v0 as v0

ROOT = Path(__file__).resolve().parents[2]
DATA = Path('E:/GNSS_Multipath_Project')
BASE = 'dataset_generation_logs/channel_modeling/'
DEFAULTS = {
    'ledger': BASE+'mainline_1023_model_v1_20261023T135341Z/stage2_ledger.csv',
    'cohort': BASE+'mainline_1023_cohort_v1_20261022T082520Z/cohort.json',
    'geometry': BASE+'mainline_1023_ephemeris_recovery_pvt_gga_20261024T072315Z/geometry_ephemeris_recovery_overlay.csv',
    'trajectory': BASE+'mainline_1023_pvt_recovery_20261024T054408Z/trajectory_window_overlay_pvt_recovered.csv',
}
PINS = {
    'ledger':'bbb8cac8338194b5527e00812a6547129a58466cc5fdd7db36b8c44bba01e551',
    'cohort':'287e891fae0cd294a85c073080611a19b7389ece46240b89cb1d5dab4df90229',
    'geometry':'a553280900046e0e1ea5a57e30b504a82453f44bdfbadc29f279e4196ca0a912',
    'trajectory':'1f7385663341d89cdb42c459c1e9d8c36a0ef4ca6f5d6a4f0c667944de0f0c93',
}
UNITS = dict(excess_delay_samples='samples',excess_delay_chips='chips',excess_path_length_m='m',
             doppler_offset_hz='Hz relative to reference',relative_power_db='relative dB')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def load_csv(path):
    if path.suffix.lower()!='.csv':raise ValueError('CSV input required')
    with path.open(encoding='utf-8-sig',newline='') as stream:return list(csv.DictReader(stream))


def dump_json(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def table(path,rows):
    flat=[]
    for row in rows:
        flat.append({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list,tuple)) else v for k,v in row.items()})
    pd.DataFrame(flat).to_csv(path,index=False,encoding='utf-8',lineterminator='\n')


def groups(frame,include_run=False):
    yield 'GLOBAL','ALL',frame
    for field in ['environment_class','scene_id'] + (['run_id','elevation_group','geometry_stratum'] if include_run else []):
        for key,group in frame.groupby(field,sort=True):yield field,str(key),group


def support_rows(paths,windows,cohort):
    rows=[]
    for scene,g in windows.groupby('scene_id',sort=True):
        tasks=[t for t in cohort['tasks'] if t['scene_id']==scene]
        stage0=sum(t['stage_counts_from_gate_a']['stage0_valid_40ms_windows'] for t in tasks)
        mpc=paths[(paths.scene_id==scene)&(paths.is_multipath==1)]
        rows.append(dict(scene_id=scene,environment_class=g.environment_class.iloc[0],run_n=len(tasks),
            stage0_valid_window_n=stage0,selected_window_n=len(g),selection_coverage_percent=len(g)/stage0*100,
            mpc_n=len(mpc),gsv_window_n=int((g.elevation_source=='GSV_MEASURED').sum()),
            derived_window_n=int((g.elevation_source=='EPHEMERIS_DERIVED').sum()),
            elevation_missing_n=int(g.elevation_deg.isna().sum()),
            position_matched_n=int((g.position_status=='POSITION_MATCHED').sum()),
            joint_window_n=int((g.elevation_deg.notna()&(g.position_status=='POSITION_MATCHED')).sum())))
    return rows


def run_analysis(paths,windows,raw,cohort,output,bootstrap):
    mpc=paths[paths.is_multipath==1].copy()
    quality=[]
    for role,flag in [('MPC',1),('DIRECT_REFERENCE',0)]:
        source=[r for r in raw if r['is_multipath']==str(flag)]
        for variable in UNITS:
            quality.append(dict(role=role,variable=variable,unit=UNITS[variable],
                                **v0.quality_summary(r.get(variable,'') for r in source)))
    table(output/'variable_data_quality.csv',quality)
    descriptive=[]
    for scope,label,g in groups(mpc,True):
        for variable in v0.VARIABLES:
            descriptive.append(dict(scope=scope,label=label,variable=variable,unit=UNITS[variable],
                scene_n=g.scene_id.nunique(),run_n=g.run_id.nunique(),
                **v0.quality_summary(g[variable])))
    table(output/'descriptive_by_group.csv',descriptive)
    supports=support_rows(paths,windows,cohort)
    table(output/'population_support_by_scene.csv',supports)
    fits=[]
    fit_scopes=[('GLOBAL','ALL',mpc)]+[('environment_class',str(k),g) for k,g in mpc.groupby('environment_class',sort=True)]
    fit_scopes += [('Urban_frozen_elevation',str(k),g) for k,g in mpc[mpc.environment_class=='Urban'].groupby('elevation_group',sort=True)]
    for scope,label,g in fit_scopes:
        for variable,families in v0.VARIABLES.items():
            for family in families:
                fit=v0.fit_distribution(g[variable],family)
                fits.append(dict(scope=scope,label=label,variable=variable,unit=UNITS[variable],
                    scene_n=g.scene_id.nunique(),interpretation='DESCRIPTIVE_ONLY' if g.scene_id.nunique()<3 else 'EXPLORATORY',**fit))
    table(output/'marginal_fit_metrics.csv',fits)
    print('Full-data marginal fits complete',len(fits),flush=True)
    scores,folds=v0.evaluate_loso(mpc,scopes=['GLOBAL']+['ENV:'+e for e in sorted(mpc.environment_class.unique())])
    score_summary=v0.summarize_scores(scores)
    paired,paired_summary=v0.paired_environment_comparison(scores)
    table(output/'scene_fold_scores.csv',scores)
    table(output/'scene_loso_summary.csv',score_summary)
    table(output/'paired_environment_scene_scores.csv',paired)
    table(output/'paired_environment_loso.csv',paired_summary)
    dump_json(output/'scene_fold_manifest.json',folds)
    print('Scene LOSO complete',len(scores),'scores',flush=True)
    relations=[];correlations=[]
    for scope,label,g in groups(mpc):
        relation=v0.scene_bootstrap_relation(g,iterations=bootstrap) if scope!='scene_id' and g.scene_id.nunique()>=3 else v0.relation_summary(g)
        relations.append(dict(scope=scope,label=label,**{**relation,'scene_n':g.scene_id.nunique()}))
        correlations+=v0.correlation_rows(g,scope+':'+label)
    table(output/'power_delay_relation.csv',relations)
    table(output/'parameter_spearman_correlations.csv',correlations)
    counts=[];count_stats=[]
    for scope,label,g in groups(windows):
        for n,freq in sorted(g.mpc_count.value_counts().items()):
            counts.append(dict(scope=scope,label=label,mpc_count=int(n),window_n=int(freq),
                               selected_window_n=len(g),proportion=float(freq/len(g))))
        count_stats.append(dict(scope=scope,label=label,scene_n=g.scene_id.nunique(),**v0.quality_summary(g.mpc_count)))
    table(output/'window_mpc_count_summary.csv',counts)
    table(output/'window_mpc_count_descriptive.csv',count_stats)
    geometry=[];elevation_relations=[]
    for scope,label,g in groups(windows):
        for source,h in g.groupby('geometry_stratum',sort=True):
            keys=set(h[v0.KEY].itertuples(index=False,name=None))
            matched=mpc[[tuple(k) in keys for k in mpc[v0.KEY].itertuples(index=False,name=None)]]
            geometry.append(dict(scope=scope,label=label,geometry_stratum=source,window_n=len(h),
                mpc_n=len(matched),scene_n=h.scene_id.nunique(),
                elevation_min=float(h.elevation_deg.min()) if h.elevation_deg.notna().any() else None,
                elevation_max=float(h.elevation_deg.max()) if h.elevation_deg.notna().any() else None,
                negative_elevation_n=int((h.elevation_deg<0).sum()),
                position_matched_n=int((h.position_status=='POSITION_MATCHED').sum())))
            for variable in v0.VARIABLES:
                finite=matched[np.isfinite(matched.elevation_deg)&np.isfinite(matched[variable])]
                rho=stats.spearmanr(finite.elevation_deg,finite[variable]).statistic if len(finite)>2 and finite.elevation_deg.nunique()>1 and finite[variable].nunique()>1 else None
                elevation_relations.append(dict(scope=scope,label=label,geometry_stratum=source,variable=variable,
                    n=len(finite),scene_n=finite.scene_id.nunique(),
                    spearman_rho=float(rho) if rho is not None else None,
                    status='EXPLORATORY_DEPENDENT_OBSERVATIONS' if finite.scene_id.nunique()>=3 else 'INSUFFICIENT_SUPPORT'))
    table(output/'geometry_condition_summary.csv',geometry)
    table(output/'elevation_parameter_relations.csv',elevation_relations)
    sensitivity=[]
    for label,g in [('ALL_STAGE2_MPC',mpc),*[(f'STAGE3:{k}',g) for k,g in mpc.groupby('stage3_persistence')],
                    *[(f'STAGE4:{k}',g) for k,g in mpc.groupby('stage4_mapping')]]:
        for variable in v0.VARIABLES:
            sensitivity.append(dict(attribute_subset=label,variable=variable,scene_n=g.scene_id.nunique(),
                **v0.quality_summary(g[variable])))
    table(output/'stage34_attribute_sensitivity.csv',sensitivity)
    analysis_columns=v0.KEY+v0.TAGS+['path_id','is_multipath','elevation_group']+v0.NUMERIC+[
        'elevation_deg','elevation_source','receiver_height_source','geometry_stratum','numeric_elevation_band',
        'stage3_persistence','stage4_mapping','position_status']
    mpc[[c for c in analysis_columns if c in mpc]].to_csv(output/'analysis_mpc_rows.csv',index=False)
    windows.to_csv(output/'selected_window_rows.csv',index=False)
    make_figures(mpc,windows,fits,output)
    return dict(quality=quality,fits=fits,loso=score_summary,paired_environment=paired_summary,power_delay=relations,
                support_by_scene=supports,correlations=correlations,fold_count=len(folds),
                failed_fit_n=sum(f['status']!='PASS' for f in fits),
                failed_or_unsupported_loso_n=sum(s['fit_status']!='PASS' for s in scores),
                window_count_frequency={str(k):int(v) for k,v in sorted(windows.mpc_count.value_counts().items())})


def make_figures(mpc,windows,fits,output):
    directory=output/'figures';directory.mkdir()
    def save(fig,name):
        fig.tight_layout();fig.savefig(directory/(name+'.png'),dpi=170)
        fig.savefig(directory/(name+'.pdf'));plt.close(fig)
    labels=['Excess delay (chips)','Signed Doppler offset (Hz)','Relative power (dB)']
    for (variable,families),label in zip(v0.VARIABLES.items(),labels):
        values=mpc[variable].to_numpy(float);values=np.sort(values[np.isfinite(values)])
        fig,axes=plt.subplots(1,3,figsize=(14,3.8))
        axes[0].hist(values,bins=50,density=True,alpha=.3,label='All finite MPC')
        axes[1].plot(values,np.arange(1,len(values)+1)/len(values),color='black',label='Empirical')
        grid=np.linspace(values.min(),values.max(),600)
        for fit in fits:
            if fit['scope']!='GLOBAL' or fit['variable']!=variable or fit['status']!='PASS':continue
            dist=v0.DISTRIBUTIONS[fit['family']];par=fit['parameters']
            axes[0].plot(grid,dist.pdf(grid,*par),label=fit['family'])
            axes[1].plot(grid,dist.cdf(grid,*par),label=fit['family'])
            supported=values[values>0] if fit['family'] in v0.POSITIVE else values
            q=np.linspace(.005,.995,120)
            axes[2].plot(dist.ppf(q,*par),np.quantile(supported,q),'.',ms=3,label=fit['family'])
        axes[0].set(xlabel=label,ylabel='Density');axes[1].set(xlabel=label,ylabel='CDF')
        axes[2].set(xlabel='Theoretical quantile',ylabel='Empirical quantile')
        for ax in axes:ax.legend(fontsize=7);ax.grid(alpha=.2)
        save(fig,'marginal_'+variable)
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    for scene,g in mpc.groupby('scene_id',sort=True):
        axes[0].scatter(g.excess_delay_chips,g.relative_power_db,s=3,alpha=.25,rasterized=True)
        relation=v0.relation_summary(g)
        if relation['slope_db_per_chip'] is not None:
            x=np.array([g.excess_delay_chips.min(),g.excess_delay_chips.max()])
            axes[1].plot(x,relation['intercept_db']+relation['slope_db_per_chip']*x,label=scene.removeprefix('F1023_'))
    axes[0].set(xlabel='Excess delay (chips)',ylabel='Relative power (dB)',title='All 8,914 MPC candidates')
    axes[1].set(xlabel='Excess delay (chips)',ylabel='OLS relative power (dB)',title='Within-scene descriptive regressions')
    axes[1].legend(fontsize=6,ncol=2);save(fig,'power_delay_scene_comparison')
    fig,axes=plt.subplots(1,3,figsize=(13,4))
    for (variable,_),label,ax in zip(v0.VARIABLES.items(),labels,axes):
        envs=list(sorted(mpc.environment_class.unique()))
        ax.boxplot([mpc[mpc.environment_class==e][variable].dropna() for e in envs],tick_labels=envs,showfliers=True,
                   flierprops=dict(marker='.',markersize=2,alpha=.3))
        ax.set(ylabel=label);ax.tick_params(axis='x',rotation=35,labelsize=7)
    save(fig,'environment_distributions')
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for scene,g in windows.groupby('scene_id',sort=True):
        freq=g.mpc_count.value_counts(normalize=True).sort_index()
        axes[0].plot(freq.index,freq.values,'o-',label=scene.removeprefix('F1023_'))
    axes[0].set(xlabel='MPC count per selected Stage2 window',ylabel='Within-scene proportion')
    for source,g in mpc.groupby('geometry_stratum',sort=True):
        if g.elevation_deg.notna().any():axes[1].scatter(g.elevation_deg,g.excess_delay_chips,s=3,alpha=.2,label=source,rasterized=True)
    axes[1].set(xlabel='Elevation (deg; source retained)',ylabel='Excess delay (chips)')
    axes[0].legend(fontsize=5);axes[1].legend(fontsize=5);save(fig,'window_counts_and_elevation_sources')


def md_table(rows,columns):
    def val(x):
        if isinstance(x,float):return f'{x:.6g}'
        if x is None:return 'NA'
        return str(x).replace('|','/')
    return '\n'.join(['| '+' | '.join(columns)+' |','| '+' | '.join(['---']*len(columns))+' |']+
                     ['| '+' | '.join(val(r.get(c)) for c in columns)+' |' for r in rows])


def write_report(summary,output):
    a=summary['population'];analysis=summary['analysis'];rel=analysis['power_delay'][0]
    q=[r for r in analysis['quality'] if r['role']=='MPC' and r['variable'] in v0.VARIABLES]
    globalfits=[r for r in analysis['fits'] if r['scope']=='GLOBAL']
    comparisons=[r for r in analysis['paired_environment'] if r['scope']=='ENV:Urban']
    height_global={r['receiver_height_source']:r for r in summary['geometry_height_support'] if r['scope']=='GLOBAL'}
    gga=height_global.get('GGA_ELLIPSOIDAL_HEIGHT',{})
    zero=height_global.get('ZERO_HEIGHT_ASSUMPTION',{})
    text=f'''# GNSS Mainline Stage2 参数统计 V0：真实数据探索报告

状态：`EXPLORATORY_V0_COMPLETE_WITH_LIMITATIONS`。Gate E/F 仍为 PENDING；本报告不是完整 CIR 信道模型或正式 Gate G 验收。

分析时间（UTC）：{summary['created_utc']}。新结果目录：`{output.as_posix()}`。

## 1. 研究总体、选择机制与身份

本次核验 {a['run_count']} 项任务、{a['scene_count']} 个录制场景、{a['path_n']} 条 Stage2 路径；其中 {a['direct_n']} 条直达/参考路径只用于参数核对，全部 {a['mpc_n']} 条 MPC 候选进入路径级分析。
Stage0 有效窗口共 {summary['stage0_valid_window_n']}，Stage2 选中窗口 {a['selected_window_n']}；选中覆盖率 {a['selected_window_n']/summary['stage0_valid_window_n']*100:.4f}%，它不是物理多径发生率。未选中 Stage0 窗口不补记为零 MPC。
Stage3/Stage4 仅作属性与敏感性描述，不筛选候选。复合键、连续 path_id、selected_L 和 cohort 标签均核对；精确窗口关联保留全部路径。
同一录制场景内多 PRN/channel 与重叠窗口具有依赖性，不能将 {a['mpc_n']} 条路径当作独立实验重复。外层验证和不确定性均按完整 scene_id。

{md_table(analysis['support_by_scene'],['scene_id','environment_class','run_n','stage0_valid_window_n','selected_window_n','selection_coverage_percent','mpc_n','gsv_window_n','derived_window_n','position_matched_n'])}

## 2. 参数定义与数据质量

原字段及单位保留。源代码 flattenStage2 定义超额时延为各路径 delaySamples 减 path 1 delaySamples；Doppler offset 为各路径 dopplerHz 减 path 1 dopplerHz；相对功率为 10log10(|alpha|²/|alpha_1|²)，源实现自带 realmin 保护，本分析没有追加 epsilon。
13 个场景 metadata 的采样率均核验为10,230,000 Hz；源配置码率1,023,000 Hz，故10 samples/chip。时延模型使用原生 chips；1 chip=10 samples=977.51710655 ns。相对功率不是绝对接收功率，相对 Doppler 不是散射体速度。
`variable_data_quality.csv` 同时报告 MPC/参考路径、原生采样点/码片/路径长度、符号、非有限值、零值和 Tukey 异常值；异常值没有自动删除。描述统计标准差和分位数只描述依赖观测行，不构成独立样本推断。
Tukey 标记按每个原字段的浮点数值计算，边界舍入可能令采样点/码片标记数稍异；这不改变任何样本或拟合。观测时延最小值0.1 chip反映当前选择后的支持，不能据正值族外推未观测的小延迟总体。功率为正的327条仍保留：参考路径不是“必然最强或已知物理LOS”的保证。

{md_table(q,['variable','finite_n','missing_n','invalid_text_n','nonfinite_n','zero_n','negative_n','mean','std','median','iqr','p5','p95','p99','min','max','tukey_outlier_n'])}

## 3. 候选边际分布与全量描述性参数

正值 Gamma/Lognormal/Weibull 固定 location=0，严格正值支持；零/负值单列且不加 epsilon。Normal/Laplace/Student-t 保留 Doppler 符号及功率 dB。所有拟合记录样本数、参数、数值状态、warnings、对数似然和训练内 AICc/BIC；参数顺序与 SciPy 一致（正值族 shape,loc,scale；Normal/Laplace loc,scale；Student-t df,loc,scale）。SciPy 解析/内部求解不暴露优化标志时明确写明，不伪造收敛标志。
本次全量描述拟合失败 {analysis['failed_fit_n']} 项；LOSO 失败或训练场景支持不足 {analysis['failed_or_unsupported_loso_n']} 项，所有记录仍保存在 CSV 中。不同变量/不同单位的对数似然不可直接比较。只有同变量、同训练总体、同支持范围的候选可比较。

{md_table(globalfits,['variable','family','n','status','parameters','loglik','aicc','bic'])}

## 4. 独立场景留出验证

每一折重新用训练场景估计参数；同 scene 所有 run、PRN/channel、重叠窗口整体留出。GLOBAL 13折，Urban 6折；其他环境在至少两个训练场景时评估，只有两个场景的环境留出后仅一个训练场景，明确记 INSUFFICIENT_SUPPORT。无随机路径/窗口拆分。
主指标是 held-out scene 的每有限观测平均 log density，再对 scene 等权宏平均。支持违反记为 -Infinity，另列正支持条件分数，绝不隐藏测试集零/负值。训练内 AICc/BIC 不代替此成绩。宏平均候选排名是探索结果，不是经过新的独立数据检验的最终模型选择。

{md_table(analysis['loso'],['scope','variable','family','fold_n','evaluated_fold_n','macro_mean_loglik','macro_std_across_scenes','support_violation_n','failed_or_unsupported_fold_n'])}

### 在相同 held-out Urban 场景上的配对比较

下表仅比较同一测试场景、同变量、同候选族的环境模型与global模型，delta为环境模型每样本对数密度减global分数，再对场景等权平均。不能直接用Urban六折均值减global十三折均值来宣称条件模型改善。

{md_table(comparisons,['variable','family','paired_scene_n','macro_delta_env_minus_global','improved_scene_n','status'])}

### 当前证据支持的候选结论

Global和Urban的时延候选中Lognormal留出宏平均最高（首轮真实运行约0.88786和1.00885 nats/观测，精确本次值以上表为准），Gamma没有因文献先验而被指定为赢家。Global Doppler的Student-t与Normal十分接近；Urban Doppler的Normal略高。功率的全量训练内AICc偏好Student-t，但跨场景宏平均Normal略高（global差约0.00166 nats），因此Normal/Student-t均保留为竞争候选，不宣称唯一稳定分布。所有拟合仍受Stage2选择、有限场景和可能的截断/离散网格影响。

逐场景成绩见 `scene_fold_scores.csv`；训练/测试场景身份见 `scene_fold_manifest.json`。逐场景差异和少量独立场景限制外推，不因路径行数多而夸大稳定性。

## 5. 功率—时延与参数依赖

全局 Spearman rho={rel['spearman_rho']:.6f}，OLS 斜率={rel['slope_db_per_chip']:.6f} dB/chip，截距={rel['intercept_db']:.6f} dB，R²={rel['r_squared']:.6f}。
按整个 scene 有放回抽样（保留全部行与重复抽中次数），{rel['bootstrap_iterations']} 次、固定seed={rel['bootstrap_seed']}，斜率95%百分位区间 [{rel['slope_ci_low']:.6f}, {rel['slope_ci_high']:.6f}]，rho区间 [{rel['rho_ci_low']:.6f}, {rel['rho_ci_high']:.6f}]。这是13个场景下的探索性块重采样区间，不是无限总体保证。
逐场景和环境关系均保留；不依据 pooled rho 单独宣称稳定物理衰减定律。初步回归只检验线性假说，不把相关性解释为因果机制，也未为提高拟合效果删除异常值。
全局线性R²约0.055，跨场景斜率差异明显，故“总体负向关联”有证据，“普适线性衰减定律”没有得到证明。

{md_table(analysis['power_delay'],['scope','label','n','scene_n','slope_db_per_chip','spearman_rho','r_squared','slope_ci_low','slope_ci_high'])}

参数两两 Spearman 见 `parameter_spearman_correlations.csv`，没有使用路径独立假设下的 p 值。Stage3/4 属性敏感性见 `stage34_attribute_sensitivity.csv`，UNMAPPED 语义保留，Stage4 path编号匹配不被解释为物理身份恒定。

## 6. 选中窗口内 MPC 数量

{json.dumps(analysis['window_count_frequency'],ensure_ascii=False)}（键为 MPC 数，值为窗口数）。合计必须为7,847。
频数、比例、分位数按全局、scene、environment 写入 `window_mpc_count_summary.csv` 和 `window_mpc_count_descriptive.csv`。本轮不拟合 Poisson/负二项或随机簇模型，也不推断全部 Stage0 窗口的多径发生率。

## 7. 环境、连续仰角与位置条件

独立场景支持为 Urban 6、Mountain/Valley 3、Highway/Open 2、Special Reflective 2。全局为主要基线，Urban 另做完整场景留出；其他环境描述结果不能替代稳定环境专属模型的证据。全量环境参数均为描述，未引入互不相关的四套物理模型。
几何窗口来源实测统计：{json.dumps(a['window_elevation_source_counts'],ensure_ascii=False)}；派生高度来源：{json.dumps(a['window_height_source_counts'],ensure_ascii=False)}。位置匹配 {a['position_matched_n']}，仰角/位置联合 {a['joint_elevation_position_n']}。
连续仰角分 GSV_MEASURED、EPHEMERIS_DERIVED_GGA_ELLIPSOIDAL_HEIGHT、EPHEMERIS_DERIVED_ZERO_HEIGHT_ASSUMPTION；冻结 High/Mid/Low 分类另作描述，不由分类反推连续角度。缺失值没有填0；负角度如有将独立标为 OUT_OF_FORMAL_RANGE，不归Low。本次有效overlay中 {gga.get('derived_window_n','NA')} 个派生高度关联窗口共享 {gga.get('distinct_height_record_n','NA')} 条GGA高度观测，按(scene_id,source_file,record_id)去重；零高假设 {zero.get('derived_window_n','NA')} 条不是实测高度。分场景可复算计数见 `geometry_height_source_support.csv`，该表不输出高度数值或源记录身份。
`geometry_condition_summary.csv` 给出来源/场景支持与范围；`elevation_parameter_relations.csv` 给出分来源、分场景的探索性关系，少于3个支持场景标 INSUFFICIENT_SUPPORT。既有独立pilot为145/145，MAE0.269477°、P950.448884°、最大0.491844°；本轮未重算，也不声称旧全量audit包含后来新增pilot身份凭据。
位置只用于覆盖/来源描述。旧空间审计36项均为 INSUFFICIENT_SPATIAL_SUPPORT，不估计空间相关距离、有效独立单元或正式空间模型；没有更改路段阈值。没有精确坐标进入本报告或Git结果。

## 8. 图表与复算

`figures/marginal_*.png`（同时有PDF）包含真实MPC经验密度、拟合密度、ECDF/理论CDF和Q-Q诊断；`power_delay_scene_comparison` 包含全部MPC散点及逐scene回归；`environment_distributions`比较四环境；`window_counts_and_elevation_sources`展示场景计数分布及分来源仰角散点。
图中每个点都来自本次真实输入；合成数据仅出现在单元测试。`analysis_mpc_rows.csv`/`selected_window_rows.csv`为本地复算数据，原账本不变；`model_summary.json`保存所有输入路径/SHA、代码SHA、库版本、设置、失败与主要结果。`artifact_manifest.json`绑定产物。

## 9. 文献方法依据与边界

1. Wang, Chen, Liu, Sensors 2018，[DOI:10.3390/s18041149](https://doi.org/10.3390/s18041149)：已核验[PubMed作者摘要](https://pubmed.ncbi.nlm.nih.gov/29642564/)中的静态城市GNSS实测参数统计及Gamma时延结论；本轮出版社全文访问受限，因此不援引未核验公式、页码或数值。功率—时延线性关系作为Commander指定的待检验假设。本轮对移动场景重新比较候选，不迁移论文参数或把其结果当本数据结论。
2. Yin et al., TVT 2016，[DOI:10.1109/TVT.2015.2506180](https://doi.org/10.1109/TVT.2015.2506180)：已核验作者机构库摘要中被动UMTS信号、CIR、SAGE参数估计和随时间变化的簇分析链条；未取得并逐式核验全文，因此不援引未核验公式/参数。机构来源：https://ir.pku.edu.cn/handle/20.500.11897/457077 。
3. Cai, Yin et al., TCOM 2016，[DOI:10.1109/TCOMM.2016.2578923](https://doi.org/10.1109/TCOMM.2016.2578923)：已核验作者机构库摘要中地铁被动测量、簇内/簇间统计与参数关联的方法方向；全文细节未核验。机构来源：https://portal.research.lu.se/en/publications/an-empirical-random-cluster-model-for-subway-channels-based-on-pa/ 。本V0没有簇追踪，不声称已建立该类随机簇模型。

## 10. 工程路线与后续验收

第一层为本次 SAGE 参数探索V0（完成并有局限），第二层为环境/几何/运动条件的初步探索（稳定共享/分层参数需更多场景证据），第三层等待Task5 CIR及Gate E/F，在完整精确窗口关联后分析CIR/PDP、Stage2选择效应、结构与时间演化。三层是同一工程递进路线。
Task5仅做小型audit/monitor和进程只读取样，记录在 `task5_readonly_snapshot.json`；生产代码、release、worker、Coordinator、监控、历史科学输出未修改。没有raw IQ/MAT/HDF5读取，没有MATLAB/SAGE/GNSS-SDR/CIR新执行。
后续最小步骤：Commander复核V0与候选差异 → Task5完成后独立Gate E/F → 精确关联完整CIR/PDP → 再评估共享条件模型、联合分布与完整结构模型。Phase-2生成AI未授权也未运行。
'''
    (output/'v0_model_report.md').write_text(text,encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root',type=Path,default=DATA)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--bootstrap',type=int,default=1000)
    for name in DEFAULTS:
        parser.add_argument('--'+name,type=Path,default=Path(DEFAULTS[name]))
        parser.add_argument('--'+name+'-sha256',default=PINS[name])
    args=parser.parse_args();started=time.perf_counter()
    if args.bootstrap<1:raise ValueError('bootstrap must be positive')
    output=args.output.resolve()
    if output.exists():raise ValueError('new-only output namespace already exists')
    # Keep all new analysis I/O in the approved isolated checkout.
    output.relative_to((ROOT/'dataset_generation_logs/channel_modeling').resolve())
    pins={};loaded={};overlay_errors=[]
    for name in DEFAULTS:
        path=(args.data_root/getattr(args,name)).resolve()
        try:
            if path.suffix not in ['.csv','.json']:raise ValueError('CSV/JSON inputs only')
            digest=sha(path)
            if digest!=getattr(args,name+'_sha256'):raise ValueError(name+' SHA256 mismatch')
            pins[name]=dict(path=path.as_posix(),sha256=digest,size_bytes=path.stat().st_size)
            if name=='cohort':loaded[name]=json.loads(path.read_text(encoding='utf-8-sig'))
            elif name=='trajectory':
                # Read useful attributes, excluding precise coordinates entirely.
                cols=v0.KEY+['scene_id','prn','tracking_channel','position_status','position_source',
                              'route_component_id','route_cumulative_distance_m','receiver_speed_mps']
                loaded[name]=pd.read_csv(path,dtype=str,keep_default_na=False,usecols=lambda c:c in cols).to_dict('records')
            else:loaded[name]=load_csv(path)
        except (ValueError,OSError) as exc:
            if name in ['ledger','cohort']:raise
            loaded[name]=None;overlay_errors.append(f'{name}: {exc}')
    raw=loaded['ledger'];cohort=loaded['cohort']
    # Fail closed on the primary population; a bad overlay only disables conditions.
    try:paths,windows,audit=v0.prepare_population(raw,cohort,loaded['geometry'],loaded['trajectory'])
    except ValueError as exc:
        paths,windows,audit=v0.prepare_population(raw,cohort)
        overlay_errors.append('condition identity validation: '+str(exc))
    if tuple(audit[k] for k in ['path_n','direct_n','mpc_n','selected_window_n','run_count','scene_count'])!=(16761,7847,8914,7847,83,13):
        raise ValueError('frozen primary population count mismatch')
    source_audit_path=pins['ledger']['path'].replace('stage2_ledger.csv','feature_audit.json')
    source_audit=json.loads(Path(source_audit_path).read_text(encoding='utf-8-sig'))
    if source_audit['audit_status']!='STAGE2_LEDGER_PASS_CIR_ASSOCIATION_PENDING' or source_audit['cohort_sha256']!=pins['cohort']['sha256']:
        raise ValueError('ledger audit status/cohort mismatch')
    pins['ledger_audit']=dict(path=source_audit_path,sha256=sha(Path(source_audit_path)))
    for run,g in paths.groupby('run_id'):
        ref=g[g.path_id==1].set_index('window_id')
        for field,absolute in [('excess_delay_samples','delay_samples'),('doppler_offset_hz','doppler_hz')]:
            expected=g[absolute].to_numpy()-g.window_id.map(ref[absolute]).to_numpy()
            if not np.allclose(expected,g[field],rtol=1e-8,atol=1e-7,equal_nan=True):raise ValueError('relative-reference numerical mismatch: '+run)
    if not np.allclose(paths.excess_delay_samples,10*paths.excess_delay_chips,rtol=1e-9,atol=1e-8,equal_nan=True):
        raise ValueError('sample/chip conversion mismatch')
    for scene in sorted(paths.scene_id.unique()):
        p=args.data_root/'scenes'/scene/'metadata.json'
        meta=json.loads(p.read_text(encoding='utf-8-sig'))
        if meta['signal']['sample_rate_hz']!=10230000:raise ValueError('sampling rate mismatch')
        pins['metadata:'+scene]=dict(path=p.as_posix(),sha256=sha(p))
    # Bind the existing audited recovery evidence; no source observations are reprocessed.
    try:
        for name,filename in [('geometry','geometry_ephemeris_recovery_audit.json'),('trajectory','trajectory_pvt_recovery_audit.json')]:
            if loaded[name] is None:continue
            p=Path(pins[name]['path']).parent/filename
            doc=json.loads(p.read_text(encoding='utf-8-sig'));pins[name+'_audit']=dict(path=p.as_posix(),sha256=sha(p))
            if name=='geometry':
                if (doc['gsv_measured_count'],doc['ephemeris_derived_count'],doc['elevation_missing_count'])!=(5128,1665,1054):raise ValueError('recovery audit count mismatch')
                if doc['input_files'][DEFAULTS['trajectory']]['sha256']!=pins['trajectory']['sha256']:raise ValueError('geometry/position provenance mismatch')
        if loaded['geometry'] is not None and not overlay_errors:
            if audit['window_elevation_source_counts']!={'GSV_MEASURED':5128,'EPHEMERIS_DERIVED':1665,'MISSING':1054} or audit['position_matched_n']!=7020 or audit['joint_elevation_position_n']!=6791:
                raise ValueError('geometry coverage count mismatch')
    except (ValueError,KeyError,OSError) as exc:
        overlay_errors.append('overlay audit validation: '+str(exc))
        paths,windows,audit=v0.prepare_population(raw,cohort)
    output.mkdir(parents=True)
    summary=dict(schema_version=1,status='EXPLORATORY_V0_COMPLETE_WITH_LIMITATIONS',
        created_utc=datetime.now(timezone.utc).isoformat(),population=audit,input_files=pins,
        overlay_errors=overlay_errors,stage0_valid_window_n=sum(t['stage_counts_from_gate_a']['stage0_valid_40ms_windows'] for t in cohort['tasks']),
        git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        code_files={p.name:sha(p) for p in [Path(__file__),Path(v0.__file__),ROOT/'scripts/channel_modeling/mainline_stage2_model_prep.py']},
        environment=dict(python=sys.version,platform=platform.platform(),numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__,matplotlib=matplotlib.__version__),
        settings=dict(bootstrap=args.bootstrap,seed=20261024,sample_rate_hz=10230000,nominal_code_rate_hz=1023000,
            fit_support='positive families fixed loc=0 and strict positive subset; unsupported held-out rows stay visible',
            validation_unit='whole scene_id',uncertainty_unit='whole scene_id with multiplicity'),
        gate_e='PENDING',gate_f='PENDING',full_cir_model='NOT_RUN')
    summary['geometry_height_support']=v0.height_source_support(loaded['geometry']) if loaded['geometry'] is not None and not overlay_errors else []
    table(output/'geometry_height_source_support.csv',summary['geometry_height_support'])
    summary['analysis']=run_analysis(paths,windows,raw,cohort,output,args.bootstrap)
    production=args.data_root/(BASE+'mainline_1023_cir_v1_20261023T123208572Z_task5batch_takeover')
    snapshot=dict(inspected_utc=datetime.now(timezone.utc).isoformat(),production_control_actions='NONE')
    for label,p in [('batch_audit',production/'cir_batch_audit.json'),
                    ('hourly_status',Path('C:/Users/Public/Documents/GNSS_Multipath_Project/Task5HourlyStatus/output/latest_status.json'))]:
        try:snapshot[label]=dict(path=p.as_posix(),contents=json.loads(p.read_text(encoding='utf-8-sig')))
        except (ValueError,OSError) as exc:snapshot[label]=dict(unavailable=str(exc))
    snapshot['production_code_sha256']={n:sha(ROOT/'scripts/channel_modeling'/n) for n in
        ['Invoke-Mainline1023CIRSingle.ps1','export_gnss_code_domain_cir.m','validate_gnss_code_domain_cir.m']}
    snapshot['completion_receipt_exists']=(production/'cir_batch_completion_receipt.json').exists()
    snapshot['stop_receipt_exists']=(production/'cir_batch_stop_receipt.json').exists()
    dump_json(output/'task5_readonly_snapshot.json',snapshot)
    summary['elapsed_seconds']=time.perf_counter()-started
    # Confirm original inputs still match the exact bytes read.
    for name,pin in pins.items():
        if sha(Path(pin['path']))!=pin['sha256']:raise ValueError('input changed during analysis: '+name)
    dump_json(output/'model_summary.json',summary)
    write_report(summary,output)
    dump_json(output/'artifact_manifest.json',{p.relative_to(output).as_posix():dict(sha256=sha(p),size_bytes=p.stat().st_size) for p in sorted(output.rglob('*')) if p.is_file()})
    print(json.dumps(dict(status=summary['status'],output=output.as_posix(),population=audit,seconds=summary['elapsed_seconds']),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
