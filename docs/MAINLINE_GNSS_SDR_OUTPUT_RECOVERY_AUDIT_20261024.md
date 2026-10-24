# Mainline GNSS-SDR 历史输出盘点与几何覆盖恢复

**检查日期：** 2026-10-24（Asia/Shanghai）

**状态：** `AUDIT_COMPLETE_WITH_LIMITATIONS`
**范围：** 冻结 cohort 的 13 个 scene、7,847 个 Stage2 窗口身份；不重跑 GNSS-SDR，不干预 CIR Task 5。

## 结论摘要

已有 GNSS-SDR 结果并非只有 Task 7 最初使用的 trajectory NMEA：13 个 scene 均有 NMEA、RINEX OBS/NAV、PVT dump、配置和成功运行记录；另外还有 tracking/telemetry/observables 与卫星仰角汇总输出。此前确实还有可利用的逐历元 PVT dump 和同一 GGA 记录中的高度字段，但没有找到能增加覆盖的独立历史备份或其他坐标格式。

在不改写旧 overlay 的前提下，产生了两个独立的新 overlay：PVT 直接历元位置恢复，以及 RINEX 广播星历派生仰角。最终几何 overlay 保留全部 7,847 个唯一 `(run_id, window_id)`，原 5,128 个 `GSV_MEASURED` 仰角完全保留，另有 1,665 个单独标记为 `EPHEMERIS_DERIVED`，1,054 个继续缺失。位置匹配从 5,540 增至 7,020；仰角与位置联合支持为 6,791/7,847（86.54%）。所有 8,914 条 MPC 与 Task 6 Stage2 ledger 均未改动。

**没有任何 scene 目前被判定为“可尝试重跑”。** 六个 scene 的当前位置/仰角恢复目标已全覆盖，`无需重跑`；其余七个还有明确缺口，但现有原始 IQ 只核验了路径存在和文件大小，未读取或验证完整性，因此按要求归类为`必须补充资料后才能判断`。不得据此启动 GNSS-SDR。

## 1. 全 cohort 文件盘点

对 13 个冻结 scene 检查了文件清单/元数据、配置、run status、日志及相关文本输出。每个 scene 均存在以下输出类别：

- `metadata.json`；GNSS-SDR 配置；`run_status.json`（`SUCCESS`、return code 0）及执行日志。
- tracking、telemetry、observables 输出。
- trajectory NMEA（含 RMC、GGA、GSV）；RINEX OBS 与 GPS NAV。
- PVT `.dat` 与 `.mat` 文件。只解析了 `.dat` PVT 记录；`.mat` 仅看文件名/大小/时间，没有打开或反序列化。
- `satellite_elevation_timeseries.csv` 与 `satellite_elevation_summary.csv`。它们是已有 NMEA 的派生物，不是独立观测来源。

所有 scene 的配置为 `PVT.positioning_mode=Single`、PVT dump 开启、输出率 1,000 ms；NMEA 与 RINEX 输出开启，GPX/KML/GeoJSON/XML 输出关闭。实际文件与配置相符：没有发现 GPX、KML、GeoJSON、XML 或 `gps_ephemeris.xml`。GNSS-SDR 文档列明 PVT 的可用输出格式及其配置项；本地配置已显式启用 NMEA/RINEX、关闭其他地理格式。[GNSS-SDR PVT 文档](https://gnss-sdr.org/docs/sp-blocks/pvt/)

下表的 NMEA 数是校验和有效的 RMC/GGA/GSV 消息数；PRN 列是解析出的 GPS 卫星号，不是 Stage2 任务数。RINEX OBS/NAV 均存在；NAV 列给出 NAV 记录数及记录覆盖的 GPS PRN。

| Scene | 有效 RMC/GGA/GSV | GSV GPS PRN | NAV 记录 / GPS PRN | 每 scene 输出类别 |
|---|---:|---|---|---|
| `F1023_V120_D0121_P2` | 518/518/1,036 | G03,G06,G11,G12,G19,G24,G25,G28,G29,G32 | 10 / G03,G06,G11,G12,G19,G24,G25,G28,G29,G32 | 上述完整输出集 |
| `F1023_v50_D0127_P1` | 20/20/38 | G11,G25,G28,G29,G31 | 5 / G11,G25,G28,G29,G31 | 上述完整输出集 |
| `F1023_V70_D0117_P2` | 21/21/42 | G06,G11,G12,G25,G28,G29,G32 | 7 / G06,G11,G12,G25,G28,G29,G32 | 上述完整输出集 |
| `F1023_V70_D0117_P4` | 16/16/32 | G11,G12,G25,G28,G29,G32 | 7 / G11,G12,G25,G28,G29,G31,G32 | 上述完整输出集 |
| `F1023_V70_D0120_P1` | 50/50/71 | G18,G26,G27,G29,G31 | 5 / G18,G26,G27,G29,G31 | 上述完整输出集 |
| `F1023_V70_D0120_P5` | 7/7/11 | G16,G18,G23,G26,G27 | 5 / G16,G18,G23,G26,G27 | 上述完整输出集 |
| `F1023_V70_D0120_P7` | 43/43/43 | G16,G18,G26,G31 | 4 / G16,G18,G26,G31 | 上述完整输出集 |
| `F1023_V70_D0120_P8` | 14/14/14 | G16,G18,G23,G26 | 4 / G16,G18,G23,G26 | 上述完整输出集 |
| `F1023_V70_D0120_P9` | 49/49/98 | G05,G16,G18,G23,G26,G27,G29,G31 | 9 / G05,G16,G18,G23,G26,G27,G28,G29,G31 | 上述完整输出集 |
| `F1023_V70_D0122_P1` | 26/26/52 | G12,G13,G14,G15,G17,G19,G22,G23,G24 | 9 / G12,G13,G14,G15,G17,G19,G22,G23,G24 | 上述完整输出集 |
| `F1023_V70_D0122_P2` | 54/54/54 | G15,G19,G23,G24 | 4 / G15,G19,G23,G24 | 上述完整输出集 |
| `F1023_V80_D0117_P8` | 20/20/36 | G12,G25,G28,G29,G31,G32 | 6 / G12,G25,G28,G29,G31,G32 | 上述完整输出集 |
| `F1023_v90_D0117_P7` | 24/24/42 | G11,G12,G25,G28,G29,G32 | 6 / G11,G12,G25,G28,G29,G32 | 上述完整输出集 |

### 重复文件与历史备份

- 主目录 NMEA 与 `full_parse_v1`、`E:\AAGNSSSDR_input\results\full_parse_v1` 中的副本，13/13 scene 字节一致。与 `trajectory/` 副本相比，12/13 完全一致；`F1023_V70_D0117_P2` 的 RMC/GGA 不同，但 GSV 记录等价，且该 scene 当前 592/592 个 Stage2 窗口已有位置与仰角支持，因此差异没有补出新的缺失窗口。
- `gnss_sdr/rinex` 的 OBS/NAV 与两处 `full_parse_v1` 副本 13/13 一致；OBS 历元数与对应 NMEA RMC/GGA 计数相符。`navigation/` 下另有 OBS/NAV：12/13 字节一致；D0117/P2 虽头部不同，NAV 仍为相同 7 条记录，OBS 的 21 个历元和 GPS PRN 语义相同。重复格式不作为独立证据。
- 两份历史 darkroom 快照只包含 D0117/P2 的 trajectory NMEA 与 NAV，均未增加新记录或覆盖。
- 9 个冻结“缺少目标卫星仰角”的任务分类都属于原 `NO_TARGET_PRN_GSV` 类。新的同 scene NAV 检查恢复了其中 6 个任务类别，共 499 个窗口：V120/D0121/P2 的 G03/ch2（96）、G19/ch0（62）、G19/ch1（74）、G19/ch3（46）；V70/D0117/P4 的 G31/ch1（116）；V70/D0120/P9 的 G28/ch11（105）。另外 3 类、229 个窗口（V70/D0122/P2 的 G10/ch6 50、G12/ch2 116、G13/ch5 63）在同一 scene 的 GSV、RINEX OBS/NAV 中均没有目标 PRN 的支持，故继续缺失。

13 个 raw IQ 路径均可从元数据看到，合计 61,986,118,144 bytes（约 57.73 GiB）。本轮没有读取其内容，也没有校验完整录制长度、数据连续性或 SHA；“路径存在”不等于“可安全重跑”。

## 2. 缺失原因与恢复方法

### 原 GSV-only overlay

2,719 个原缺失仰角窗口分类如下：

| 原 missing_reason | 窗口数 |
|---|---:|
| `NO_TARGET_PRN_GSV` | 728 |
| `GSV_GAP_OR_CADENCE_LIMIT` | 725 |
| `NO_TEMPORAL_OVERLAP` | 1,266 |

全场景的 RINEX NAV 和逐历元 PVT 输出之前没有进入 Task 7 的几何 overlay 流程，是可恢复部分的来源。NMEA 导出的 satellite elevation summary/timeseries 是 GSV 的派生，不会填补独立观测。

### PVT 位置 overlay

原 NMEA 位置为 5,540/7,847。13 个 PVT `.dat` 共解析 44,623 条 RTKLIB 单点 XYZ 记录；被接受的记录具有有效单点状态和至少 4 颗卫星。以 Stage2 的 GPS 接收时刻与 PVT `rx_time` 作同 scene 直接历元匹配，沿用不超过 0.5 秒的原时间门限，不插值、不外推；新匹配 1,480，最终 7,020/7,847，827 个位置仍缺失。旧 trajectory overlay 未修改。

剩余 827 个位置窗口全部逐一对照了两份现有 NMEA：在既有 0.5 秒准则内没有新的有效 RMC/GGA 解。其成因对应 375 个轨迹真实不连续窗口和 452 个观测路线覆盖范围外窗口；不是通过跨断点插值或范围外外推补齐。

### RINEX 星历派生仰角 overlay

先在 `F1023_V120_D0121_P2` 做 pilot，再运行一次 13-scene cohort overlay。计算只用同 scene、精确 GPS PRN、健康且 `|t-toe|≤7,200 s` 的 GPS LNAV 广播星历，并用已有匹配位置；已有 GSV 一律优先。未满足位置/星历条件的身份保留并给出具体缺失原因。

| 仰角来源/状态 | 窗口数 | 说明 |
|---|---:|---|
| `GSV_MEASURED` | 5,128 | 与旧 overlay 完全保留，不替换 |
| `EPHEMERIS_DERIVED` | 1,665 | 新计算，绝不标为实测或写回冻结分类 |
| 仍缺失 | 1,054 | 825 `NO_VALID_POSITION`；229 `NO_HEALTHY_EPHEMERIS_FOR_PRN_WITHIN_2H` |

派生值中的 622 个窗口使用了精确时刻、同 scene GGA 的高度（由 GGA 正高加大地水准面差得到椭球高）；它们只对应 55 条不同的物理 GGA 记录，不能当作 622 个独立高度观测。其余 1,043 个派生窗口明确采用 `ZERO_HEIGHT_ASSUMPTION`，存在高度近似误差。GGA 的高度字段为相对于平均海水面的正高，另有大地水准面差字段；这一字段语义可见 [Trimble GGA 字段说明](https://help.fieldsystems.trimble.com/r10/nmea0183-messages-gga.htm)。本 overlay 不含纬度/经度列、原始 NMEA 句子或精确坐标；同时保留位置/高度的来源与假设字段。

Pilot 与同 scene 已有 GSV 仰角比较 145 个同时具备 GSV 和有效位置的窗口：MAE 0.2695°、P95 绝对误差 0.4489°、最大误差 0.4918°、145/145 在 1° 内，signed bias −0.1953°。其中 136 条比较使用精确 GGA 高度，9 条使用零高度假设。它是特定数据上的一致性检查，不是独立测量真值，也不能证明 13 个 scene 的误差都相同。

### 最终逐 scene 覆盖

| Scene | 环境 | Stage2 窗口 | GSV | 星历派生 | 仰角缺失 | 位置匹配 | 联合匹配 | 联合覆盖 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| F1023_V120_D0121_P2 | Highway/Open | 841 | 145 | 468 | 228 | 613 | 613 | 72.89% |
| F1023_v50_D0127_P1 | Urban | 386 | 104 | 68 | 214 | 172 | 172 | 44.56% |
| F1023_V70_D0117_P2 | Mountain/Valley | 592 | 451 | 141 | 0 | 592 | 592 | 100.00% |
| F1023_V70_D0117_P4 | Mountain/Valley | 761 | 566 | 195 | 0 | 761 | 761 | 100.00% |
| F1023_V70_D0120_P1 | Urban | 330 | 293 | 37 | 0 | 330 | 330 | 100.00% |
| F1023_V70_D0120_P5 | Urban | 483 | 257 | 66 | 160 | 321 | 321 | 66.46% |
| F1023_V70_D0120_P7 | Urban | 439 | 408 | 31 | 0 | 439 | 439 | 100.00% |
| F1023_V70_D0120_P8 | Urban | 447 | 332 | 34 | 81 | 366 | 366 | 81.88% |
| F1023_V70_D0120_P9 | Special Reflective | 987 | 792 | 195 | 0 | 987 | 987 | 100.00% |
| F1023_V70_D0122_P1 | Urban | 842 | 639 | 157 | 46 | 796 | 796 | 94.54% |
| F1023_V70_D0122_P2 | Special Reflective | 669 | 344 | 15 | 310 | 588 | 359 | 53.66% |
| F1023_V80_D0117_P8 | Highway/Open | 449 | 369 | 80 | 0 | 449 | 449 | 100.00% |
| F1023_v90_D0117_P7 | Mountain/Valley | 621 | 428 | 178 | 15 | 606 | 606 | 97.58% |
| **Total** |  | **7,847** | **5,128** | **1,665** | **1,054** | **7,020** | **6,791** | **86.54%** |

按环境的联合覆盖率：Urban 2,424/2,927（82.82%）；Highway/Open 1,062/1,290（82.33%）；Mountain/Valley 1,959/1,974（99.24%）；Special Reflective 1,346/1,656（81.28%）。这些是窗口覆盖描述，不代表独立样本数；重叠窗口不能作为相互独立观测。

## 3. 重跑建议

| 结论 | Scene | 依据 |
|---|---|---|
| `无需重跑`（针对本次位置/仰角覆盖恢复目标） | V70/D0117/P2、V70/D0117/P4、V70/D0120/P1、V70/D0120/P7、V70/D0120/P9、V80/D0117/P8 | 位置和仰角均已覆盖该 scene 的全部 Stage2 窗口；重跑不会解决当前已识别缺口。 |
| `必须补充资料后才能判断` | V120/D0121/P2、v50/D0127/P1、V70/D0120/P5、V70/D0120/P8、V70/D0122/P1、V70/D0122/P2、v90/D0117/P7 | 仍有位置或仰角缺口；但 raw IQ 内容/完整性未验证，现有配置已启用 NMEA、RINEX 与 1 Hz PVT dump，尚无证据说明仅重跑相同配置就能增加有效解。 |

因此当前没有符合证据门槛的 `可尝试重跑` scene。后续若要提出重跑方案，先补齐 raw IQ 完整性与录制区间证据、逐 scene 的目标卫星可观测性分析，并说明拟更改的 GNSS-SDR 输出/采样设置及预期新增记录。即便重处理相同 IQ，也不能保证能恢复没有足够卫星观测、没有定位解或不在录制时间范围内的窗口。未获 Commander 明确批准前不得运行。

## 4. 身份、产物和限制

- 两个输出均写入新的隔离 namespace：
  - `E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\mainline_1023_pvt_recovery_20261024T054408Z\`
  - `E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\mainline_1023_ephemeris_recovery_pvt_gga_20261024T072315Z\`
- PVT 恢复输出的 SHA-256：位置 overlay `1F7385663341D89CDB42C459C1E9D8C36A0EF4CA6F5D6A4F0C667944DE0F0C93`；PVT audit `B41015DD79F72E4FA58381F303AF1ECCF7FCE1BB83E74B29B32CAC7F79C5DD54`。
- 最终仰角 overlay、scene summary、missing-reason summary 与 audit 的 SHA-256：
  - overlay `A553280900046E0E1EA5A57E30B504A82453F44BDFBADC29F279E4196CA0A912`
  - by-scene `B7719A00A20D6811DEB9D56F19C5C52905E1C035DB91E1A4C8878AA3B5819D6B`
  - missing reasons `6248D511CE54960B9D60E30FA859F80AB2F51EE5AFE9950AD9080B34EED84E66`
  - audit `33567AB2BD21FB683C8EB39A936E6096EC741AA45BB354534E6AA4D0798E3163`
- Final overlay independently reconciles exactly to the old 7,847 `(run_id,window_id)` keys; GSV count remains 5,128; derived+missing classifications sum to 2,719; the CSV contains no latitude/longitude columns or raw NMEA sentences.
- Frozen Stage2 ledger SHA-256 remains `BBB8CAC8338194B5527E00812A6547129A58466CC5FDD7DB36B8C44BBA01E551`; Task 6 ledger, 8,914 MPC rows, original geometry/trajectory overlays and prior outputs were not modified.
- Task 5 was inspected read-only at 2026-10-24 15:48:39 +08: the batch scheduled task and G25/ch5 task were `Running`; MATLAB process pair 50112/45984 had creation time 13:46:35 +08; existing 30-minute monitor was `Ready`, last run 15:35:01, next run 16:05:00. No Task 5 stage, release content, or scientific output was read or changed, and no process/task was controlled. This is a single sample, not a continuing status claim.
- No raw IQ content was read or hashed; no MAT/HDF5 payload was opened; no GNSS-SDR, MATLAB, SAGE, or CIR production was run.
- The 9 frozen missing-elevation task classifications, Stage2 MPC inclusion, frozen elevation categories, Gate F, and model claims remain unchanged. `EPHEMERIS_DERIVED` is a derived geometry feature only, not a GSV measurement and not a reason to rewrite the frozen task classification.

### Targeted verification

- `python -m unittest scripts.channel_modeling.tests.test_mainline_rinex_ephemeris_geometry -v`: **17/17 PASS**.
- `python -m unittest scripts.channel_modeling.tests.test_mainline_gnss_sdr_pvt_recovery -v`: **7/7 PASS**.
- `python -m py_compile` on the four new implementation/runner modules: **PASS**.
- Re-run GSV pilot for `F1023_V120_D0121_P2`: **PASS**, 145 comparisons, statistics above.
- Independent CSV identity/count reconciliation: **PASS**, 7,847 exact unique key set; coordinate columns/raw sentences absent.
- The generated runtime audit binds input hashes but does not embed source-code hashes. The four implementation files below were hashed for this handoff; their observed modification times precede their respective output creation times.

| Implementation file | SHA-256 |
|---|---|
| `scripts/channel_modeling/mainline_rinex_ephemeris_geometry.py` | `20627EC64B4D21DA8084E7CC7E6CD2F41FEC1718EBD816D61E9747BE4E07613B` |
| `scripts/channel_modeling/run_mainline_rinex_ephemeris_recovery.py` | `82C64FE44BD1C75F547DC054FFEC3C47C7010D7EA7E158DE1B1C8C63C600C93E` |
| `scripts/channel_modeling/mainline_gnss_sdr_pvt_recovery.py` | `9C086B0B1B4DB88124AF6E04923D4C0C960824B5AE908427474DCB7B20F9E523` |
| `scripts/channel_modeling/run_mainline_gnss_sdr_pvt_recovery.py` | `A6559A842165835C7C60E6576973077D2E633B8214C9725259D90CF3CF5DF3D9` |
