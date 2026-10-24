"""Targeted, synthetic-only contracts; never used as experimental evidence."""
import sys
import unittest
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mainline_stage2_v0 as v0
import fit_mainline_1023_stage2_model as runner


def fixture():
    tasks, rows, geometry, trajectory = [], [], [], []
    for s in range(3):
        run, scene = f"run{s}", f"scene{s}"
        tag = dict(run_id=run, scene_id=scene, prn="G01", tracking_channel="1", environment_class="Urban")
        tasks.append(dict(tag, elevation_group="MISSING",stage_counts_from_gate_a={'stage0_valid_40ms_windows':10}))
        for w in range(1, 5):
            for p in [1, 2]:
                rows.append(dict(tag, window_id=str(w), path_id=str(p), selected_L="2",
                    is_multipath=str(p-1), modeling_role="DIRECT_REFERENCE" if p==1 else "MPC_CANDIDATE",
                    elevation_group="MISSING", delay_samples=str(0.2+(p-1)*(w+s+1)), excess_delay_samples=str((p-1)*(w+s+1)),
                    excess_delay_chips=str((p-1)*(w+s+1)/10), excess_path_length_m=str((p-1)*(w+s+1)*29.305),
                    doppler_hz=str(100+(p-1)*w), doppler_offset_hz=str((p-1)*w),
                    relative_power_db=str(-(p-1)*(w+s+1)), stage3_persistence="NOT_PERSISTENT",
                    stage4_mapping="UNMAPPED", recording_time_s=str(w)))
            geometry.append(dict(tag,window_id=str(w),frozen_elevation_group="MISSING",
                elevation_source="GSV_MEASURED",elevation_value_deg="20",receiver_height_source="",
                receiver_position_status="POSITION_MATCHED"))
            trajectory.append(dict(tag,window_id=str(w),position_status="POSITION_MATCHED",position_source="EXISTING_NMEA"))
    return rows, dict(tasks=tasks, eligible_count=3), geometry, trajectory


class V0Tests(unittest.TestCase):
    def test_fractional_selected_order_cannot_be_truncated_into_valid_identity(self):
        rows,cohort,geo,pos=fixture()
        rows=[r for r in rows if not(r['window_id']=='1' and r['path_id']=='2')]
        for r in rows:
            if r['window_id']=='1':r['selected_L']='1.5'
        with self.assertRaisesRegex(ValueError,'integral'):
            v0.prepare_population(rows,cohort,geo,pos)

    def test_height_record_count_distinguishes_windows_from_unique_source_records(self):
        rows=[]
        for scene in ['a','b']:
            for _ in range(2):rows.append(dict(scene_id=scene,elevation_source='EPHEMERIS_DERIVED',
                receiver_height_source='GGA_ELLIPSOIDAL_HEIGHT',receiver_height_record_id='same-line',receiver_height_source_file=scene+'/nmea'))
        rows.append(dict(scene_id='a',elevation_source='EPHEMERIS_DERIVED',receiver_height_source='ZERO_HEIGHT_ASSUMPTION'))
        summary=v0.height_source_support(rows)
        global_gga=next(r for r in summary if r['scope']=='GLOBAL' and r['receiver_height_source']=='GGA_ELLIPSOIDAL_HEIGHT')
        self.assertEqual((global_gga['derived_window_n'],global_gga['distinct_height_record_n']),(4,2))
        self.assertEqual(next(r for r in summary if r['scope']=='GLOBAL' and r['receiver_height_source']=='ZERO_HEIGHT_ASSUMPTION')['distinct_height_record_n'],0)

    def test_environment_comparison_pairs_identical_held_out_scenes(self):
        rows=[]
        for scope,scene,score in [('GLOBAL','a',-2.),('GLOBAL','b',-100.),('ENV:Urban','a',-1.)]:
            rows.append(dict(scope=scope,held_out_scene_id=scene,variable='relative_power_db',family='normal',
                fit_status='PASS',mean_loglik=score,finite_test_n=10))
        pairs,summary=v0.paired_environment_comparison(rows)
        self.assertEqual(len(pairs),1)
        self.assertEqual(summary[0]['paired_scene_n'],1)
        self.assertEqual(summary[0]['macro_delta_env_minus_global'],1.0)

    def test_missing_identity_label_and_out_of_range_measured_value_are_rejected(self):
        rows,cohort,geo,pos=fixture()
        for g in geo:del g['prn']
        with self.assertRaisesRegex(ValueError,'schema'):
            v0.prepare_population(rows,cohort,geo,pos)
        rows,cohort,geo,pos=fixture();geo[0]['elevation_value_deg']='-1'
        with self.assertRaisesRegex(ValueError,'measured'):
            v0.prepare_population(rows,cohort,geo,pos)

    def test_negative_derived_elevation_is_preserved_outside_formal_bins(self):
        rows,cohort,geo,pos=fixture()
        geo[0].update(elevation_source='EPHEMERIS_DERIVED',receiver_height_source='ZERO_HEIGHT_ASSUMPTION',elevation_value_deg='-1')
        _,windows,_=v0.prepare_population(rows,cohort,geo,pos)
        self.assertEqual(windows.iloc[0].numeric_elevation_band,'OUT_OF_FORMAL_RANGE')
        self.assertEqual(windows.iloc[0].elevation_deg,-1.0)
    def test_real_analysis_orchestration_writes_consistent_tables_and_figures(self):
        raw,cohort,geo,pos=fixture()
        paths,windows,_=v0.prepare_population(raw,cohort,geo,pos)
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            result=runner.run_analysis(paths,windows,raw,cohort,out,10)
            self.assertEqual(sum(result['window_count_frequency'].values()),12)
            self.assertEqual(result['power_delay'][0]['scene_n'],3)
            self.assertTrue((out/'scene_fold_scores.csv').is_file())
            self.assertEqual(len(list((out/'figures').glob('*.png'))),6)

    def test_population_preserves_mpc_and_selected_window_counts(self):
        paths, windows, audit = v0.prepare_population(*fixture())
        self.assertEqual((len(paths),len(windows),int(paths.is_multipath.sum())),(24,12,12))
        self.assertEqual(windows.mpc_count.tolist(),[1]*12)
        self.assertEqual(audit['scene_count'],3)

    def test_overlay_join_rejects_cross_task_channel_and_duplicate(self):
        rows, cohort, geo, pos = fixture()
        geo[0]['tracking_channel']='9'
        with self.assertRaisesRegex(ValueError,'identity'):
            v0.prepare_population(rows,cohort,geo,pos)
        rows,cohort,geo,pos=fixture()
        geo.append(geo[0].copy())
        with self.assertRaisesRegex(ValueError,'duplicate'):
            v0.prepare_population(rows,cohort,geo,pos)

    def test_overlay_partial_set_fails_without_dropping_paths(self):
        rows,cohort,geo,pos=fixture()
        with self.assertRaisesRegex(ValueError,'window set'):
            v0.prepare_population(rows,cohort,geo[:-1],pos)

    def test_population_rejects_duplicate_and_noncanonical_path_keys(self):
        rows,cohort,geo,pos=fixture()
        with self.assertRaisesRegex(ValueError,'duplicate'):
            v0.prepare_population(rows+[rows[0]],cohort,geo,pos)
        rows[0]['window_id']='01'
        with self.assertRaisesRegex(ValueError,'canonical'):
            v0.prepare_population(rows,cohort,geo,pos)

    def test_direct_rows_never_enter_mpc_population_and_zero_counts_survive(self):
        rows,cohort,geo,pos=fixture()
        rows=[r for r in rows if not(r['window_id']=='1' and r['path_id']=='2')]
        for r in rows:
            if r['window_id']=='1':r['selected_L']='1'
        paths,windows,_=v0.prepare_population(rows,cohort,geo,pos)
        self.assertEqual(int(paths.is_multipath.sum()),9)
        self.assertEqual(int((windows.mpc_count==0).sum()),3)

    def test_quality_keeps_zero_negative_nonfinite_and_missing_accounting(self):
        q=v0.quality_summary(['', 'bad', 'NaN','Inf','-1','0','2','4'])
        self.assertEqual((q['total_n'],q['missing_n'],q['invalid_text_n'],q['nonfinite_n'],q['finite_n']), (8,1,1,2,4))
        self.assertEqual((q['zero_n'],q['negative_n'],q['median']),(1,1,1.0))

    def test_normal_mle_and_score_are_hand_checkable(self):
        fit=v0.fit_distribution([1,2,3,4], 'normal')
        self.assertEqual(fit['status'],'PASS')
        np.testing.assert_allclose(fit['parameters'],[2.5,np.sqrt(1.25)])
        self.assertAlmostEqual(v0.score_fit(fit,[2.5])['mean_loglik'], -np.log(np.sqrt(1.25)*np.sqrt(2*np.pi)))

    def test_positive_families_never_epsilon_fill_or_hide_support_violation(self):
        for name in ['gamma','lognormal','weibull']:
            fit=v0.fit_distribution([-1,0,1,2,3,4,5,6,7,8],name)
            self.assertEqual(fit['n'],8)
            self.assertEqual(fit['excluded_nonpositive_n'],2)
            self.assertEqual(fit['parameters'][1],0)
            score=v0.score_fit(fit,[0,2])
            self.assertEqual(score['mean_loglik'],'-Infinity')
            self.assertEqual(score['support_violation_n'],1)

    def test_failed_fit_is_a_visible_record(self):
        fit=v0.fit_distribution([1]*10,'student_t')
        self.assertEqual(fit['status'],'FAILED')
        self.assertTrue(fit['failure_reason'])

    def test_loso_refits_with_scene_wholly_held_out_and_macro_equal_scene(self):
        paths,_,_=v0.prepare_population(*fixture())
        mpc=paths[paths.is_multipath==1]
        scores,folds=v0.evaluate_loso(mpc,variables={'relative_power_db':['normal']},scopes=['GLOBAL'])
        self.assertEqual(len(scores),3)
        for fold in folds:
            self.assertNotIn(fold['held_out_scene_id'],fold['training_scene_ids'])
            self.assertEqual(fold['train_n'],8)
            self.assertEqual(fold['test_n'],4)
        self.assertEqual([s['fit_parameters'][0] for s in scores],[-5.0,-4.5,-4.0])
        summary=v0.summarize_scores(scores)[0]
        self.assertAlmostEqual(summary['macro_mean_loglik'],np.mean([s['mean_loglik'] for s in scores]))

    def test_scene_bootstrap_preserves_cluster_draws_and_is_deterministic(self):
        paths,_,_=v0.prepare_population(*fixture())
        mpc=paths[paths.is_multipath==1]
        a=v0.scene_bootstrap_relation(mpc,iterations=40,seed=9)
        b=v0.scene_bootstrap_relation(mpc,iterations=40,seed=9)
        self.assertEqual(a,b)
        self.assertAlmostEqual(a['slope_db_per_chip'],-10)
        self.assertAlmostEqual(a['slope_ci_low'],-10)
        self.assertEqual(a['bootstrap_unit'],'whole_scene_with_multiplicity')

    def test_geometry_missing_never_becomes_zero_and_height_source_is_separate(self):
        rows,cohort,geo,pos=fixture()
        geo[0].update(elevation_source='MISSING',elevation_value_deg='')
        geo[1].update(elevation_source='EPHEMERIS_DERIVED',receiver_height_source='ZERO_HEIGHT_ASSUMPTION')
        paths,windows,_=v0.prepare_population(rows,cohort,geo,pos)
        self.assertTrue(np.isnan(windows.iloc[0].elevation_deg))
        self.assertEqual(windows.iloc[1].geometry_stratum,'EPHEMERIS_DERIVED_ZERO_HEIGHT_ASSUMPTION')
        self.assertEqual(len(paths),24)


if __name__=='__main__':unittest.main()
