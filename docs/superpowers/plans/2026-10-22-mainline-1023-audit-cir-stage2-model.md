# Mainline 10.23 MHz 数据审计、CIR 名单冻结与 Stage2 建模实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 本文是计划，不是执行回执；各任务的 `PASS` 须由将来的实际输出证明。

**Goal:** 在不补跑 SAGE 的前提下，以当前83项已完成 Mainline rerun 为唯一输入范围，先审计并冻结 CIR/建模任务身份，之后安全提取 code-domain CIR，建立以所有 Stage2 MPC 为总体的新版本信道模型，并将验证结果交接。

**Architecture:** Manifest/Summary 与已完成产物为只读上游；审计报告和不可变83项 cohort 清单固定输入；CIR 采用独立版本目录、单任务新建输出、每项 QA 后发布；建模只消费 QA 通过的 Stage2/alpha/CIR 派生数据，在新命名空间生成模型和独立评估。任一门禁失败时停止当前阶段，不悄悄缩小或更改冻结名单。

**Tech Stack:** PowerShell 7 / Python 3（CSV/JSON 审计与统计）、MATLAB（现有 CIR/alpha 实现的最小参数化）、HDF5（按块验证）、定向回归测试、SHA-256（文本/代码/清单/小型 CSV 发布绑定）、Windows 正常用户单实例执行链。

**Spec:** 用户 2026-10-22 本轮决策；工程事实与策略见 `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md` 第106、115节。旧 Phase-1/r3 模型与单任务 CIR pilot 是独立历史结果，不是本计划已完成的批量成果。

## Global Constraints

- 当前权威输入：`reports/data_consolidation_20261003/MAINLINE_SAGE_1023_RERUN_MANIFEST.csv`、`MAINLINE_SAGE_1023_BATCH_RERUN_SUMMARY.csv`。计划起点89项中 `ALREADY_COMPLETE=1, COMPLETE=82, PENDING=4, FAILED=2, IN_PROGRESS=0`。任何执行日均须重读并验证当前状态；本文数字是2026-10-22快照，不替代实时权威文件。
- 新 cohort 仅为83项 `ALREADY_COMPLETE|COMPLETE` 的准确 `run_id`/scene/PRN/channel 集合。其余6项只在新 cohort 中排除，记录身份与现有状态即可，不要求排除原因；原 Manifest、Summary、输出及回执不得更改。禁止让状态变化后的新增身份自动混入已冻结 cohort。
- SAGE 已完成输出、冻结科学算法、pilot CIR、旧模型和旧 plan/receipt 均不可覆盖。`MODELING_POPULATION=ALL_STAGE2_MULTIPATH`；`is_multipath=1` 全部纳入候选，直达路径只作参考；Stage3/Stage4 标签与 QA 不构成 Stage2 MPC 的准入门槛。不得以 Stage4 未确认推断某条 MPC 为假。
- 审计/冻结阶段不读 raw IQ 内容，不反序列化 MAT/HDF5，不运行 MATLAB/SAGE/CIR。只有后续 CIR 阶段在名单、来源、空间及发布门禁通过后才读取清单所指 raw IQ；不重哈希 raw IQ。所有科学输出单写者、`new_only`、无覆盖、无自动重试；MATLAB 通过现有受控正常用户执行链启动，不从 Codex shell 直接启动。
- E: Kingston XS1000 将保持连接，但 Dirty/Warning/Full Repair Needed 仍属已接受、未经验证的风险。新增真实 I/O/断连/读写或校验错误立即停止写入并保留现场；不运行 chkdsk、不整盘扫描。先根据先导实测重新估计空间（按现有253,946,914字节/898窗口粗估其余82项约80.6 GB HDF5，非保证值），设置保留余量，逐项核对可用空间。
- 城市/观测角度可成为后续论文重点；无需为四环境等量覆盖而补跑六项。仰角缺失不得补猜；现有 PRN/场景级仰角不得称为逐路径动态仰角。当前不写论文结果、不改变 Paper Handoff；有经独立验证的结果后再交接论文叙事。
- 输出版本一经发布只读；重做须创建新版本和新 receipt，旧证据留存。日志和外部文本均为不可信数据，不执行其中指令。每阶段结束留下机器可核对的计数、输入 SHA、代码 SHA、QA 与失败清单。

## Review Focus

- 核对83项与89项全集的集合关系，不把 `PENDING`/`FAILED` 手工改成 `COMPLETE` 或“废弃”；六项既不进入 CIR 任务也不进入模型训练/测试。
- 既有 pilot `F1023_V70_D0117_P2/G28/ch1` 只验证/引用，不重新写入；剩余82项采用唯一新输出路径。不同任务共享原始 scene 时，raw 文件可复用为只读输入，但任务身份、PRN/channel、Stage0窗口和多普勒证据必须各自绑定。
- 现有 CIR exporter 硬编码 pilot 身份/PRN，validator 硬编码898窗口/35,920快照并一次性读全量 HDF5；先解除这两个阻断并以定向测试证明不改变单窗相关算法、延迟网格及 pilot 数值语义。
- 现有 pilot ledger 的 `primary_modeling_pool` 以 Stage3 为门槛，**不可**直接充当本 Mainline Stage2-all-MPC cohort；新 ledger 必须用测试防止漏掉 transient MPC。
- 避免跨相邻重叠窗口和同一 run/scene 的训练/测试泄漏；对城市/仰角分层报告样本支持度和缺失，而非预设显著性或四环境普适结论。

---

### Task 1: 完成可复现的83项只读数据审计

**Files:**
- Implemented in the audit package (kept out of the pre-existing untracked source tree): `reports/data_consolidation_20261003/mainline_1023_model_v1/audit_20261022T071844Z/audit_mainline_1023_stage2_cohort.py` and `test_audit_mainline_1023_stage2_cohort.py`
- Generate, new-only: `reports/data_consolidation_20261003/mainline_1023_model_v1/audit_20261022T074307Z/audit.json`、`audit.md`、`task_audit.csv`、`eligible_runs.csv`、`excluded_runs.csv`

**Interfaces:** 输入只读 Manifest、Summary、十任务最终 batch receipt、83项输出路径/relocation receipts、Stage0–Stage4 CSV、scene metadata 与可得仰角表；输出逐项审计与聚合计数。MAT/HDF5/raw IQ 只查存在性、路径、大小和 mtime；不打开载荷。`excluded_runs.csv` 只含6个 run_id、状态与身份字段，不写原因。

- [x] 重读 CSV 原始字节 SHA；核对89个 run_id 唯一、身份在 Manifest/Summary 一致、状态计数恰为1/82/4/2/0；失败时只写审计失败记录，不冻结名单。
- [x] 对83项逐一核对最终命名空间、Stage0–Stage4 必需文件/空表合法性、receipt 身份/路径/状态、Summary 计数/退出码；在文本 CSV 上检查键唯一、有限值、`selected_L`/选中路径关系及 Stage2 `is_multipath` 分类。不得把仅有文件当作 QA 通过。
- [x] 聚合并守恒：13场景、23 PRN、Stage0 285,752窗口；Stage2 16,761选中路径 = 7,847直达 + 8,914 MPC；Stage3 persistent 2,228、Stage4 strict confirmed 120。与权威 Summary 和完成 receipt 比较，记录每项差异；数值不符则止步。
- [x] 审计环境、每 scene/run 任务数、Stage2 MPC 数、观测角度来源与缺失。确认环境任务分布为 Urban 6场景/29项、Mountain/Valley 3/20、Highway/Open 2/18、Special Reflective 2/16；9项 scene+PRN 仰角摘要缺失，未插补。
- [x] 定向测试15/15通过，覆盖身份错位、重复 path key、缺失 receipt、Stage2 计数不守恒、合法 Stage4 空表、仰角缺失、非 eligible 身份排除及预期 invalid-model `Inf` sentinel；真实数据只读审计为83/83 task PASS、0 error、9条缺失仰角 warning。审计器与测试 SHA 记录在 `audit.json`。

**Gate A: PASS（2026-10-22 UTC）。** 最终审计没有身份、计数、receipt 或结构矛盾；9条warning均为已保留的仰角元数据缺失，不阻断下一步。首轮校准报告 `audit_20261022T071844Z` 保留，曾把 invalid-model 的合法 `Inf` sentinel和 Stage0 schema/Stage4 规则误判为错误；规则修正并通过回归后，以新目录 `audit_20261022T074307Z` 完成正式 PASS，不覆盖首轮证据。未冻结名单。

### Task 2: 冻结建模与 CIR 的同一83项身份集合

**Files:**
- Add: `scripts/channel_modeling/freeze_mainline_1023_cohort.py`
- Add: `scripts/channel_modeling/tests/test_freeze_mainline_1023_cohort.py`
- Generate, new-only: `dataset_generation_logs/channel_modeling/mainline_1023_cohort_v1_<UTC>/cohort.json`、`cir_tasks.json`、`cohort_validation.json`

**Interfaces:** `cohort.json` 每项固定 `run_id,scene_id,prn,tracking_channel,output_namespace,source_summary_status` 与 Stage CSV/receipt 定位、源文件 SHA/必要元数据；头部固定 Manifest/Summary 原始字节 SHA、审计 SHA、人数83、population policy。`cir_tasks.json` 从**同一** cohort 自动派生：pilot 一项 `EXISTING_VALIDATED`，82项 `NEW_REQUIRED`，不得自行重新筛选。清单不包含六个未完成身份。

- [x] 在写清单前再次读取权威 CSV 并与 Gate A 的 SHA/状态比较；若变化，重新审计而非追认旧清单。
- [x] 按 run_id 稳定排序、精确身份匹配，冻结83项与6项排除状态；证明 `83 + 6 = 89`、无交集/重复、pilot 恰好一次、82个新 CIR 任务。六项不要求排除原因。
- [x] 对清单输出使用不可变带 UTC 版本目录、源 SHA 和清单自身 SHA；若同名目录/文件存在则拒绝覆盖。发布后只读；任何改动必须新版本且引用前一版。
- [x] 定向测试 stale Summary、错误 PRN/channel、重复项、pilot 重复、把6项纳入、输出碰撞。真实 `--validate-only` 必须 PASS 后才生成正式清单。

**Gate B: PASS（2026-10-22 UTC）。** 发布前重新核对的 Manifest/Summary SHA 分别为 `52edba87ee8c6726ea905a3f79879c5351131f9f78fd9120c0881e9473731ac5` 与 `9e0d3845b463e98cae96f23a05b6d12eb72a0e42ad3bc71e06a72dd9a9e4cffc`，与 Gate A 绑定一致；状态为 `1/82/4/2/0`（ALREADY_COMPLETE/COMPLETE/PENDING/FAILED/IN_PROGRESS）。定向测试 `test_freeze_mainline_1023_cohort` 7/7 PASS，当前 `--validate-only` PASS。不可变工件：`dataset_generation_logs/channel_modeling/mainline_1023_cohort_v1_20261022T082520Z/`；cohort SHA-256 `287e891fae0cd294a85c073080611a19b7389ece46240b89cb1d5dab4df90229`，derived `cir_tasks.json` SHA-256 `2acbf20f64e961d9391550e3fcef3f3ee66d602f01c456e30c0a47a3c4c10d41`。83项/6项精确分区、唯一身份、既有 pilot 一次、82项 NEW_REQUIRED 已核实。未读取 raw IQ 内容/重算其哈希，未打开 MAT/HDF5 载荷，未运行 MATLAB/SAGE/CIR；未改权威 CSV、既有输出或回执。

### Task 3: 仅针对批量阻断参数化现有 CIR exporter 与 validator

**Files:**
- Modify minimally: `scripts/channel_modeling/export_gnss_code_domain_cir.m`
- Modify minimally: `scripts/channel_modeling/validate_gnss_code_domain_cir.m`
- Extend: `scripts/channel_modeling/tests/test_code_domain_cir_snapshot.m`
- Add targeted test: `scripts/channel_modeling/tests/test_mainline_cir_multi_identity.m`

**Interfaces:** 冻结 `cohort.json` → `cir_tasks.json` SHA 链绑定唯一任务身份、PRN/channel 与输出 namespace；cohort 行的 Stage0/Stage2 路径及 SHA 必须与调用者输入完全相同且位于该任务 namespace。只接受项目根下已批准的 `scene_metadata_10MHz.csv`，由精确 scene 行解析 raw 路径、10.23 MHz 采样率与字节数；scene metadata 本身也须有 SHA pin。期望 raw 字节数仍须绑定 Gate A `task_audit.csv` 中同一 `run_id` 的 `raw_iq_size_bytes`（这些值不声称存放在 `cir_tasks.json` 中），Task 4 `ValidateOnly` 必须验证 scene metadata SHA 和 raw-size pin 与冻结文件/精确 Gate A 行一致。Exporter 对实际 `run_nav_sage_pipeline.m` 与 `default_sage_configuration.m` 校验部署 SHA，并确认 MATLAB 从该 project root 解析配置文件。三个 CIR 输出必须是不同的规范化路径。保持当前 10.23 MHz 配置、40×1ms/Stage0窗口、451延迟 bin、PDP 算法与 pilot 标定限制。按实际窗口数推导 `40 × N` 快照，不硬编码898/35,920；分块写/读 HDF5，内存上限由先导任务验证。

- [x] TDD RED/GREEN 与合成多身份覆盖完成：非 pilot 身份/两窗口重叠导出、身份与采样率错误、raw 大小变化、Stage0/2 source path 与 SHA 授权、scene metadata SHA、部署源码/config pin、输出路径别名、缺失 Stage0 映射、重复窗口、输出碰撞、截断 HDF5、PDP 不匹配、Stage0 对齐错误及末块不足均有定向用例。最终 multi-identity suite 22/22 PASS；snapshot 数学 suite 2/2 PASS；合计24/24 PASS。
- [x] 最小解除 pilot 身份与 PRN 常量：同时校验冻结 `cohort.json`/`cir_tasks.json` 哈希链与准确 run_id 行；Stage0/Stage2 路径和 SHA 精确绑定 cohort 行。校验项目根中的 frozen SAGE entry (`BFFC123C…`) 与默认配置 (`AC06AD31…`) 实际 SHA，并确认 MATLAB 解析路径正确。raw 路径与字节数必须与 `scene_metadata_10MHz.csv` 的唯一 scene 行一致，runner 提供的字节数还须经 Task 4 与同一 `run_id` 的 Gate A `task_audit.csv` 行绑定。未改 frozen SAGE core、snapshot 数学 helper、归一化选择或 Stage2–Stage4 门禁。
- [x] Validator 已按实际窗口数和 64 行 HDF5 chunk 验证结构、有限值、顺序、Stage0 对齐并逐窗重算 PDP；每个窗口最多保留40×451数值用于严格零容差比较，不整体载入完整 CIR。
- [x] 部署配置根目录专项验证完成：显式指向 `E:\GNSS_Multipath_Project` 的合成测试通过。Task 4 后续在隔离 release namespace 对 G28/ch1 做了只读 HDF5 baseline read-back，并对 G18/ch2、G23/ch0 完成了真实 pilot 与新旧数值比较；均未重写既有 pilot。

**Gate C:** 定向测试通过；跨身份、跨窗口数无错误硬编码；pilot 语义未回归；否则不批量放行。

**Gate C: PASS（2026-10-23 UTC）。** 实际 G28/ch1 baseline read-back 与 G18/ch2、G23/ch0 两个真实 pilot 的 source/identity、数值对照、PDP重算、轴对齐、HDF5 read-back 与 receipt 均已通过；测试和边缘数值限制见 `docs/CIR_TASK4_PILOT_ACCEPTANCE_20261023.md`。G23 存在一个 dominant PDP peak 落在冻结 delay grid 上界的窗口，已如实记录，不据此改算法或 QA 门槛。

### Task 4: 完成先导 CIR、发布顺序运行配置

**Files:**
- Add: `scripts/channel_modeling/Invoke-Mainline1023CIRSingle.ps1`（如现有受控 runner 可直接复用，则仅加最小参数层）
- Add: `scripts/channel_modeling/tests/Invoke-Mainline1023CIRSingle.Tests.ps1`
- Generate, new-only: `dataset_generation_logs/channel_modeling/mainline_1023_cir_v1_<UTC>/release_request.json`、`runs/<run_id>/...`、`pilot_audit.json`

- [x] 两个精确 run_id 的 `-ValidateOnly` 均通过，`MATLAB_INVOKED=false`、`RAW_CONTENT_READ=false`；G28/ch1 read-back PASS，旧 HDF5 size/mtime unchanged。详细 report/release evidence 保存于 immutable release root。
- [x] 冻结名单内选择不同 Urban 场景、不同可用仰角档的 G18/ch2（P1/High）及 G23/ch0（P5/Low）；既有 G28/ch1 只读验收，未重导出或覆盖。
- [x] 正常 Windows 用户的串行 launcher 分别只执行一次 G18、G23，G23 仅在 G18 所有验收通过后启动。两项均 MATLAB exit0、HDF5/PDP/轴与身份 QA、比较 CSV、独立输出哈希和 per-run receipt 全 PASS；G18 40m32.46s，G23 6m39.49s。没有自动重试。Post-pilot code review 发现的跨 release 重复启动风险及请求策略/JSON 类型校验缺口已在 runner 中做最小 fail-closed 修复：使用 batch 级 run_id 原子 reservation，并严格检查 source pin 键和值类型及固定执行策略；修复版 runner 测试55/55通过。原 pilot release/request/source SHA 和计算结果均未改动；未来新生产必须由新 immutable request 绑定新 runner SHA。
- [x] 以两项 pilot 的实测 bytes/window 与运行吞吐更新80项剩余预测；含25% margin 的 HDF5 上界149.17 GiB、运行估算94.03h（慢 pilot 情景115.35h），E: 当时408.35 GiB free，可保留100 GiB余量。AGC未知按 relative/un-calibrated 幅度处理。预测和 G23 grid-edge 限制见 pilot acceptance report；此 Gate 不放行批量生产。

**Gate D: PILOTS PASS / BULK HELD (2026-10-23 UTC).** Pilot 验收及当时空间预算通过；E: 的既存 Dirty/Warning 风险仍未验证，且用户明确要求先独立审查 Task 3/4，不启动其余80项。此处只记录样例阶段通过，不表示批量 CIR 生产获准。

### Task 5: 串行提取并审计剩余 CIR

**Files:**
- Reuse: `scripts/channel_modeling/Invoke-Mainline1023CIRSingle.ps1`、Task 3 MATLAB exporter/validator
- Generate, new-only: 同版 `.../runs/<run_id>/`、`cir_run_receipts/<run_id>.json`、`cir_batch_audit.json`

- [ ] 每轮只从冻结清单选择仍为 `NEW_REQUIRED` 且无成功 receipt 的下一个身份；最多一个 MATLAB worker，逐项 `ValidateOnly → export → chunked QA → receipt → publish`。不重跑先导/pilot，不覆盖已有输出。
- [ ] 每项保存运行身份、Stage0窗口数、snapshot数、451-bin 网格、PDP误差、输入/代码/清单 SHA、E:空间前后、输出文件元数据及失败现场。异常停批；不自动重试。每次生产写入前确认无新 I/O/断连/校验失败。
- [ ] 总验收：83项清单 = 1项既有 pilot + 82项新 CIR；每项都有有效 QA/receipt，缺项、重复、跨身份串用或 partial 一律 FAIL。汇总 Stage0↔CIR 覆盖和缺失，不把 Stage2 未选窗误称未导出。

**Gate E:** 83/83 清单项 CIR 有证据且批次审计 PASS；仅此时将“批量 CIR 完成”写入 Engineering Handoff。失败则保留已成功项，不谎称全量完成。

### Task 6: 构建 Stage2 全MPC 数据账本与建模输入

**Files:**
- Reuse with scope check: `scripts/channel_modeling/export_stage2_complex_alpha.m`
- Add Mainline-specific ledger builder, or narrowly extend with explicit policy: `scripts/channel_modeling/build_mainline_1023_stage2_ledger.py`
- Add: `scripts/channel_modeling/tests/test_mainline_1023_stage2_ledger.py`
- Generate, new-only: `dataset_generation_logs/channel_modeling/mainline_1023_model_v1_<UTC>/stage2_ledger.csv`、`feature_audit.json`、per-run alpha sidecars/receipts as needed

- [ ] 只读83项 Stage2/3/4 CSV，若需要 complex alpha 才通过受控路径读取相应 Stage2 MAT 的选中模型；alpha 不得作为 Stage2 MPC 纳入条件。保留 pilot 的窗口归一化 alpha 语义与接收机校准限制。
- [ ] 新 ledger 每条选中路径恰好一行，以 `(run_id,window_id,path_id)` 唯一；`is_multipath=1` 的8,914条全部在候选总体，7,847直达单列参考。Stage3 persistent 与 Stage4 confirmed/unmapped 只作三态/多态标签，不把未映射当 NO。既有 Stage3-gated pilot ledger 保留不改。
- [ ] 只在有可靠同 scene/PRN 元数据时联结仰角档，记录匹配来源、粒度和缺失；不用其他时间/PRN 猜测。CIR/PDP 特征必须按准确 Stage0 window_id 与 Stage2 window_id 对齐，并记录是否重叠或无选中路径。
- [ ] 对行数守恒、有限值、单位、键唯一、直接/多径分离、alpha 对齐、CIR 对齐和缺失进行测试；产出机器可读 feature audit。若总数不等于16,761/7,847/8,914，或出现身份冲突，停止建模。

**Gate F:** 新输入表与冻结清单、Stage2 全 MPC 策略、CIR QA 一致；无泄漏或静默删行。

### Task 7: 拟合、对照并独立验证新版本模型

**Files:**
- Add: `scripts/channel_modeling/fit_mainline_1023_stage2_model.py`
- Add: `scripts/channel_modeling/tests/test_fit_mainline_1023_stage2_model.py`
- Generate, new-only: 同版 `.../model_spec.json`、`fits/`、`evaluation/`、`model_card.md`、`model_receipt.json`

- [ ] 先登记分析单元与候选量：每 Stage2-evaluated window 的 MPC 数、每 MPC 的 excess delay、Doppler offset、relative power；通过 Gate E/F 后可加入 CIR/PDP delay-spread/形状特征。区分路径级、窗口级、run级，不将重叠窗口当独立重复测量。
- [ ] 分组按 scene/run 阻断训练/验证泄漏；记录每组支持度、缺失及切分 seed。至少比较 pooled Stage2 模型与 Urban 子集；若仰角档支持足够再做 Urban×仰角分层，缺失档单独报告。Highway/Open 与 Special Reflective 可只作描述/外部检验，不是本轮论文方向的硬门槛。
- [ ] 预先固定候选分布/模型复杂度与评估指标；以 held-out scene/run、置信区间/块自助法及预测校准/残差检查比较。没有足够独立 scene 或分层时降级为描述性结果，不制造泛化或显著性结论。
- [ ] 模型卡写明83项/8,914 MPC 的选择机制、六项未纳入、仰角粒度/缺失、Stage3/4 标签性质、CIR/AGC 限制、归一化功率语义，以及城市聚焦的适用范围；对模型参数、训练代码和输入 cohort 保存 SHA 与 receipt。旧 Phase-1/r3 模型不改不覆。

**Gate G:** 输入审计、分组验证、模型卡、独立复核全部 PASS 后才能称 `MODEL_VALIDATED`；拟合脚本退出0本身不是验收。

### Task 8: 收口与论文交接

**Files:**
- Update after real execution: `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`
- Update only with validated scientific results: `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`
- Generate: 本版 cohort/CIR/model 的 final audit 与可追溯 artifact 清单

- [ ] 按 Gate A–G 实际通过项分别写 `Completed/Validated/Planned/Failed`，包括83项身份、CIR覆盖、Stage2 MPC 守恒、模型泛化边界、真实路径和 SHA；失败阶段保持原状态，不把“计划”改写为“完成”。
- [ ] 与用户确认论文是否采用 Urban/仰角主线，再同步 Paper Handoff 的科学叙事、图表需求和限制；不要求为了四环境对称而补跑六项。
- [ ] 最终独立核对新版本所有 receipts/QA 与冻结 cohort；在明确无未解决偏差后交付简明数据与模型可用性报告。

## 本次交付边界

截至2026-10-23 UTC：Task 1/Gate A、Task 2/Gate B、Task 3/Gate C 和 Task 4 baseline + G18/G23 pilot 验收已完成；Task 5 的80项 CIR serial batch 已获单独授权并开始生产，最新检查样本见工程交接手册第95节。Task 6 的 Stage2 全路径账本及83项统计已生成，16,761行守恒、7,847 direct reference、8,914 MPC候选，具体结果见 reports/data_consolidation_20261003/mainline_1023_model_v1/task6_stage2_ledger_summary_20261023.md。这只是 Stage2 ledger 的阶段性通过：CIR/PDP精确关联、HDF5 read-back 和 Gate F 仍待 Task 5 完成；本计划不表示 CIR 特征已齐或已建模。
