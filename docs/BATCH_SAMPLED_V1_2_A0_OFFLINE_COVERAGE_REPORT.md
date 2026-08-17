# batch-sampled-v1.2 A0 Offline Coverage Report

- Planner: `batch-sampled-v1.2-a0`
- Rule hash: `531aa8368779ba4eac3833468a9580d091c75c79d678346e0135eeeea1ddc0ea`
- Selection freeze hash: `76e1c4e5779ef7538a0d6fee5728594634167687d83e595119f821061aa27c27`
- Scope: 11 fixed 10.23 MHz gold tasks; Stage0 and verified TOW-aligned geometry only during selection.
- Raw IQ/MATLAB/SAGE: not read or executed.
- `gold_labels_used_for_selection=false`: confirmed; Stage3/Stage4 were opened only after selection manifests were frozen.

## Decision

**FAIL** — the hard gate requires every reference and Wave-A known confirmed event center and its ±2 closure to reach 100% recall in every reported budget profile. A0 is not permitted as the sole production promoter unless this gate passes.

## Per-task/profile replay

| task | budget | N0 | Npromoted | components | Nfine | initial center | final center | initial ±2 | final ±2 | Stage3 closure | budget exhausted | inconclusive | geometry |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| reference_F1023_V70_D0117_P2_G06_ch4 | 1200 | 319 | 27 | 5 | 46 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | verified |
| reference_F1023_V70_D0117_P2_G06_ch4 | 2400 | 319 | 27 | 5 | 46 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | verified |
| reference_F1023_V70_D0117_P2_G06_ch4 | 4800 | 319 | 27 | 5 | 46 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | verified |
| reference_F1023_V70_D0117_P2_G11_ch5 | 1200 | 1175 | 23 | 3 | 35 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | verified |
| reference_F1023_V70_D0117_P2_G11_ch5 | 2400 | 1175 | 23 | 3 | 35 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | verified |
| reference_F1023_V70_D0117_P2_G11_ch5 | 4800 | 1175 | 23 | 3 | 35 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | verified |
| reference_F1023_V70_D0117_P2_G12_ch6 | 1200 | 1175 | 38 | 1 | 42 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | verified |
| reference_F1023_V70_D0117_P2_G12_ch6 | 2400 | 1175 | 38 | 1 | 42 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | verified |
| reference_F1023_V70_D0117_P2_G12_ch6 | 4800 | 1175 | 38 | 1 | 42 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | verified |
| reference_F1023_V70_D0117_P2_G25_ch0 | 1200 | 1175 | 54 | 2 | 62 | n/a | n/a | n/a | n/a | n/a | 0 | 0 | verified |
| reference_F1023_V70_D0117_P2_G25_ch0 | 2400 | 1175 | 54 | 2 | 62 | n/a | n/a | n/a | n/a | n/a | 0 | 0 | verified |
| reference_F1023_V70_D0117_P2_G25_ch0 | 4800 | 1175 | 54 | 2 | 62 | n/a | n/a | n/a | n/a | n/a | 0 | 0 | verified |
| reference_F1023_V70_D0117_P2_G28_ch1 | 1200 | 898 | 45 | 4 | 55 | n/a | n/a | n/a | n/a | 0.0% | 0 | 0 | verified |
| reference_F1023_V70_D0117_P2_G28_ch1 | 2400 | 898 | 45 | 4 | 55 | n/a | n/a | n/a | n/a | 0.0% | 0 | 0 | verified |
| reference_F1023_V70_D0117_P2_G28_ch1 | 4800 | 898 | 45 | 4 | 55 | n/a | n/a | n/a | n/a | 0.0% | 0 | 0 | verified |
| reference_F1023_V70_D0117_P2_G29_ch7 | 1200 | 1175 | 46 | 3 | 58 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | verified |
| reference_F1023_V70_D0117_P2_G29_ch7 | 2400 | 1175 | 46 | 3 | 58 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | verified |
| reference_F1023_V70_D0117_P2_G29_ch7 | 4800 | 1175 | 46 | 3 | 58 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | verified |
| reference_F1023_V70_D0117_P2_G32_ch11 | 1200 | 1175 | 22 | 2 | 30 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | verified |
| reference_F1023_V70_D0117_P2_G32_ch11 | 2400 | 1175 | 22 | 2 | 30 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | verified |
| reference_F1023_V70_D0117_P2_G32_ch11 | 4800 | 1175 | 22 | 2 | 30 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | verified |
| waveA_F1023_V70_D0120_P7_G16_ch1 | 1200 | 2229 | 0 | 0 | 0 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | verified |
| waveA_F1023_V70_D0120_P7_G16_ch1 | 2400 | 2229 | 0 | 0 | 0 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | verified |
| waveA_F1023_V70_D0120_P7_G16_ch1 | 4800 | 2229 | 0 | 0 | 0 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | verified |
| waveA_F1023_v50_D0127_P1_G25_ch0 | 1200 | 2339 | 118 | 13 | 110 | n/a | n/a | n/a | n/a | n/a | 0 | 1 | unavailable |
| waveA_F1023_v50_D0127_P1_G25_ch0 | 2400 | 2339 | 118 | 13 | 110 | n/a | n/a | n/a | n/a | n/a | 0 | 1 | unavailable |
| waveA_F1023_v50_D0127_P1_G25_ch0 | 4800 | 2339 | 118 | 13 | 110 | n/a | n/a | n/a | n/a | n/a | 0 | 1 | unavailable |
| waveA_F1023_V70_D0122_P1_G12_ch6 | 1200 | 1629 | 0 | 0 | 0 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | verified |
| waveA_F1023_V70_D0122_P1_G12_ch6 | 2400 | 1629 | 0 | 0 | 0 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | verified |
| waveA_F1023_V70_D0122_P1_G12_ch6 | 4800 | 1629 | 0 | 0 | 0 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 | 0 | verified |
| wave2A_F1023_V120_D0121_P2_G11_ch0 | 1200 | 15210 | 245 | 20 | 321 | n/a | n/a | n/a | n/a | n/a | 0 | 0 | verified |
| wave2A_F1023_V120_D0121_P2_G11_ch0 | 2400 | 15210 | 245 | 20 | 321 | n/a | n/a | n/a | n/a | n/a | 0 | 0 | verified |
| wave2A_F1023_V120_D0121_P2_G11_ch0 | 4800 | 15210 | 245 | 20 | 321 | n/a | n/a | n/a | n/a | n/a | 0 | 0 | verified |

## Controls

Promotion is a coarse coverage decision, not a multipath label. `not_promoted` is not LOS. The following controls are reported to expose promotion behavior only:

| task | budget | score P10 | P50 | P90 | max | promotion fraction | components | Nfine | geometry |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| reference_F1023_V70_D0117_P2_G25_ch0 | 1200 | 0.151043363 | 0.29308016 | 0.723682769 | 3.13451106 | 4.6% | 2 | 62 | verified |
| reference_F1023_V70_D0117_P2_G25_ch0 | 2400 | 0.151043363 | 0.29308016 | 0.723682769 | 3.13451106 | 4.6% | 2 | 62 | verified |
| reference_F1023_V70_D0117_P2_G25_ch0 | 4800 | 0.151043363 | 0.29308016 | 0.723682769 | 3.13451106 | 4.6% | 2 | 62 | verified |
| reference_F1023_V70_D0117_P2_G28_ch1 | 1200 | 0.156532615 | 0.310566524 | 0.87257742 | 3.15952885 | 5.0% | 4 | 55 | verified |
| reference_F1023_V70_D0117_P2_G28_ch1 | 2400 | 0.156532615 | 0.310566524 | 0.87257742 | 3.15952885 | 5.0% | 4 | 55 | verified |
| reference_F1023_V70_D0117_P2_G28_ch1 | 4800 | 0.156532615 | 0.310566524 | 0.87257742 | 3.15952885 | 5.0% | 4 | 55 | verified |
| waveA_F1023_v50_D0127_P1_G25_ch0 | 1200 | 0.182140219 | 0.374518534 | 1.33982196 | 3.06590589 | 5.0% | 13 | 110 | unavailable |
| waveA_F1023_v50_D0127_P1_G25_ch0 | 2400 | 0.182140219 | 0.374518534 | 1.33982196 | 3.06590589 | 5.0% | 13 | 110 | unavailable |
| waveA_F1023_v50_D0127_P1_G25_ch0 | 4800 | 0.182140219 | 0.374518534 | 1.33982196 | 3.06590589 | 5.0% | 13 | 110 | unavailable |
| wave2A_F1023_V120_D0121_P2_G11_ch0 | 1200 | 0.158017702 | 0.31100163 | 0.730620682 | 3.01551759 | 1.6% | 20 | 321 | verified |
| wave2A_F1023_V120_D0121_P2_G11_ch0 | 2400 | 0.158017702 | 0.31100163 | 0.730620682 | 3.01551759 | 1.6% | 20 | 321 | verified |
| wave2A_F1023_V120_D0121_P2_G11_ch0 | 4800 | 0.158017702 | 0.31100163 | 0.730620682 | 3.01551759 | 1.6% | 20 | 321 | verified |

## Oracle-free failure analysis

A missed event is classified only after the frozen replay, using `score_below_threshold`, `component_gap`, `budget_exhausted`, `continuity_missing`, `geometry_unavailable`, or `inconclusive`. No rule or threshold was changed in response to an event position.

| task | budget | event center | reason | score | feature missing | component |
|---|---:|---:|---|---:|---|---|
| reference_F1023_V70_D0117_P2_G06_ch4 | 1200 | 203 | score_below_threshold | 0.312341175 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| reference_F1023_V70_D0117_P2_G06_ch4 | 1200 | 264 | score_below_threshold | 0.14141082 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| reference_F1023_V70_D0117_P2_G06_ch4 | 2400 | 203 | score_below_threshold | 0.312341175 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| reference_F1023_V70_D0117_P2_G06_ch4 | 2400 | 264 | score_below_threshold | 0.14141082 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| reference_F1023_V70_D0117_P2_G06_ch4 | 4800 | 203 | score_below_threshold | 0.312341175 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| reference_F1023_V70_D0117_P2_G06_ch4 | 4800 | 264 | score_below_threshold | 0.14141082 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| reference_F1023_V70_D0117_P2_G11_ch5 | 1200 | 640 | score_below_threshold | 0.18430608 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| reference_F1023_V70_D0117_P2_G11_ch5 | 2400 | 640 | score_below_threshold | 0.18430608 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| reference_F1023_V70_D0117_P2_G11_ch5 | 4800 | 640 | score_below_threshold | 0.18430608 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| reference_F1023_V70_D0117_P2_G12_ch6 | 1200 | 970 | score_below_threshold | 0.203136628 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| reference_F1023_V70_D0117_P2_G12_ch6 | 1200 | 971 | score_below_threshold | 0.225818379 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| reference_F1023_V70_D0117_P2_G12_ch6 | 2400 | 970 | score_below_threshold | 0.203136628 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| reference_F1023_V70_D0117_P2_G12_ch6 | 2400 | 971 | score_below_threshold | 0.225818379 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| reference_F1023_V70_D0117_P2_G12_ch6 | 4800 | 970 | score_below_threshold | 0.203136628 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| reference_F1023_V70_D0117_P2_G12_ch6 | 4800 | 971 | score_below_threshold | 0.225818379 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| reference_F1023_V70_D0117_P2_G29_ch7 | 1200 | 80 | score_below_threshold | 0.908182229 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q;vehicle_speed_kmh_value |  |
| reference_F1023_V70_D0117_P2_G29_ch7 | 2400 | 80 | score_below_threshold | 0.908182229 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q;vehicle_speed_kmh_value |  |
| reference_F1023_V70_D0117_P2_G29_ch7 | 4800 | 80 | score_below_threshold | 0.908182229 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q;vehicle_speed_kmh_value |  |
| reference_F1023_V70_D0117_P2_G32_ch11 | 1200 | 82 | score_below_threshold | 0.638708555 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q;vehicle_speed_kmh_value |  |
| reference_F1023_V70_D0117_P2_G32_ch11 | 1200 | 84 | score_below_threshold | 0.568811139 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q;vehicle_speed_kmh_value |  |
| reference_F1023_V70_D0117_P2_G32_ch11 | 2400 | 82 | score_below_threshold | 0.638708555 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q;vehicle_speed_kmh_value |  |
| reference_F1023_V70_D0117_P2_G32_ch11 | 2400 | 84 | score_below_threshold | 0.568811139 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q;vehicle_speed_kmh_value |  |
| reference_F1023_V70_D0117_P2_G32_ch11 | 4800 | 82 | score_below_threshold | 0.638708555 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q;vehicle_speed_kmh_value |  |
| reference_F1023_V70_D0117_P2_G32_ch11 | 4800 | 84 | score_below_threshold | 0.568811139 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q;vehicle_speed_kmh_value |  |
| waveA_F1023_V70_D0120_P7_G16_ch1 | 1200 | 1337 | score_below_threshold | 0.409191426 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| waveA_F1023_V70_D0120_P7_G16_ch1 | 1200 | 1338 | score_below_threshold | 0.236227162 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| waveA_F1023_V70_D0120_P7_G16_ch1 | 1200 | 1406 | score_below_threshold | 0.220397724 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| waveA_F1023_V70_D0120_P7_G16_ch1 | 1200 | 2079 | score_below_threshold | 0.22090554 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| waveA_F1023_V70_D0120_P7_G16_ch1 | 2400 | 1337 | score_below_threshold | 0.409191426 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| waveA_F1023_V70_D0120_P7_G16_ch1 | 2400 | 1338 | score_below_threshold | 0.236227162 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| waveA_F1023_V70_D0120_P7_G16_ch1 | 2400 | 1406 | score_below_threshold | 0.220397724 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| waveA_F1023_V70_D0120_P7_G16_ch1 | 2400 | 2079 | score_below_threshold | 0.22090554 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| waveA_F1023_V70_D0120_P7_G16_ch1 | 4800 | 1337 | score_below_threshold | 0.409191426 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| waveA_F1023_V70_D0120_P7_G16_ch1 | 4800 | 1338 | score_below_threshold | 0.236227162 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| waveA_F1023_V70_D0120_P7_G16_ch1 | 4800 | 1406 | score_below_threshold | 0.220397724 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| waveA_F1023_V70_D0120_P7_G16_ch1 | 4800 | 2079 | score_below_threshold | 0.22090554 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| waveA_F1023_V70_D0122_P1_G12_ch6 | 1200 | 835 | score_below_threshold | 0.430905866 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| waveA_F1023_V70_D0122_P1_G12_ch6 | 1200 | 836 | score_below_threshold | 0.54248219 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| waveA_F1023_V70_D0122_P1_G12_ch6 | 1200 | 1278 | score_below_threshold | 0.595572795 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| waveA_F1023_V70_D0122_P1_G12_ch6 | 2400 | 835 | score_below_threshold | 0.430905866 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| waveA_F1023_V70_D0122_P1_G12_ch6 | 2400 | 836 | score_below_threshold | 0.54248219 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| waveA_F1023_V70_D0122_P1_G12_ch6 | 2400 | 1278 | score_below_threshold | 0.595572795 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| waveA_F1023_V70_D0122_P1_G12_ch6 | 4800 | 835 | score_below_threshold | 0.430905866 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| waveA_F1023_V70_D0122_P1_G12_ch6 | 4800 | 836 | score_below_threshold | 0.54248219 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |
| waveA_F1023_V70_D0122_P1_G12_ch6 | 4800 | 1278 | score_below_threshold | 0.595572795 | carrier_doppler_rate_hz;carrier_lock_test;code_error_chips;code_error_filt_chips;code_freq_rate_chips;early;late;prompt_i;prompt_q |  |

## Method and safeguards

- Stage0 remains the complete mother set; every window receives an A0 feature row.
- Rolling MAD and derivatives stop at window/sample/TOW discontinuities.
- High/low hysteresis, a fixed two-window bridge, one-window boundary expansion, and ±2 closure are frozen in the rule hash.
- A budget accepts complete component + boundary + closure units. It never truncates an over-budget unit; such a unit is `inconclusive`.
- Verified geometry comes only from the v1.1 TOW-aligned diagnostic. Wave-A G25 remains `warning_fallback` and its elevation/azimuth/SNR are missing.
- Stage3/Stage4 are posterior gold sources, not promoter inputs. Stage1 rows were not needed for this center/closure replay.

## Next action
Do not run a sampled pilot and do not keep tuning A0 against gold. Proceed to the design-specified minimal B1/B2/C1 raw-coarse prototype on G16, Wave-A G25, and Wave-2A G11; this prototype is not part of A0 and must be separately approved.
