# Urban 连续 SAGE：研究设计与数据验收

本目录记录 Urban GPS L1 C/A 连续多径研究的**审计和设计阶段**。截至 2026-11-01，尚未实现或运行新的动态 SAGE，也未对真实 IQ 执行批量生产估计。

| 文件 | 用途 |
| --- | --- |
| 01_DATA_READINESS_AUDIT_CN.md | 86 段逐项复核、双采样率 IQ 格式、时间与仰角证据、研究就绪性 |
| 02_2020_TVT_METHOD_ANALYSIS_CN.md | 2020 TVT 原文方法、页码/公式定位及适配边界 |
| 03_OBSERVATION_MODEL_COMPARISON_CN.md | 直接 IQ 与重建复数相关器的数学和计算比较 |
| 04_DYNAMIC_SAGE_DESIGN_V1_CN.md | 连续动态 SAGE、关联、生灭、寿命的设计方案 |
| 05_SYNTHETIC_VALIDATION_PLAN_CN.md | 双采样率合成 IQ 真值验证与通过依据 |
| evidence/segment_audit_86.csv | 脱敏的逐片段样本、时长和证据复核摘要 |
| evidence/recording_readiness.csv | 10 份录制的脱敏状态汇总 |

## 证据边界

原始 IQ、GNSS-SDR MAT/NMEA、精确 PVT 坐标、全部逐历元 GSV 和本机绝对路径只保留在独立数据目录。公开仓库只收录脱敏摘要。2020 TVT 论文原始 PDF 不上传；正式引用：Xin Chen, Yu Jade Morton, Wenxian Yu, Trieu-Kien Truong, “GPS L1CA/BDS B1I Multipath Channel Measurements and Modeling for Dynamic Land Vehicle in Shanghai Dense Urban Area,” IEEE Transactions on Vehicular Technology 69(12), 14247–14263, 2020, DOI: [10.1109/TVT.2020.3038646](https://doi.org/10.1109/TVT.2020.3038646)。

设计中的数值门限是**待通过合成真值和保留样本标定的参数**，不得把设计文本当作已验证的生产算法。数据结论区分本轮重算、既有审计和待验证假设。
