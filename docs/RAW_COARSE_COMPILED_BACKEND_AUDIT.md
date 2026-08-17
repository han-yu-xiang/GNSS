# Raw-coarse compiled backend audit

审计日期：2026-08-12  
项目：`E:\GNSS_Multipath_Project`  
范围：只读本机环境审计、固定 microbenchmark、v2 preflight；未运行正式 G16/G25 raw-coarse Phase A，未运行 G11、MATLAB 或 SAGE。

## 结论

本机确实存在一个可审计的 compiled numeric backend 候选：

`D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe`

该解释器可以直接 import NumPy 2.5.1、SciPy 1.18.0 和 PyTorch 2.11.0+cu128，NumPy 使用 OpenBLAS，PyTorch CPU/MKLDNN 可用。

但是，当前 `run_batch_sampling_raw_coarse_v1_2_v2.py` 的 NumPy kernel 在固定 G16 microbenchmark 中未通过数值一致性门槛，因此不能把该环境直接用于正式 Phase A。

状态应记录为：

```text
COMPILED_BACKEND_FOUND=true
FORMAL_PHASE_A_ALLOWED=false
ENVIRONMENT_BLOCKED_FOR_CURRENT_KERNEL=true
G11_ALLOWED=false
```

这不是依赖缺失问题，而是“已有 backend 找到，但当前 NumPy 实现尚未通过科学一致性门禁”。

## 审计约束

- 没有联网。
- 没有执行 `pip install`、`uv install` 或其他下载/安装操作。
- 没有复制其他项目的 DLL、site-packages 或 wheel。
- 没有修改 PATH、系统环境变量、注册表或任何 venv。
- 没有修改 `run_nav_sage_pipeline.m`、scene、metadata、inventory、`sage_results` 或既有 prototype 结果。
- 没有读取 G16/G25 大规模 raw 任务；只读取固定 microbenchmark 所需的 4 个 Stage0 窗口。

## 发现的 Python 环境

| 候选 | 结果 | 版本/架构 | 数值库 |
|---|---|---|---|
| `C:\Users\Jing_\AppData\Local\Programs\Python\Python312\python.exe` | 可执行 | CPython 3.12.9, AMD64 | NumPy/SciPy/Numba/PyTorch 均不可 import |
| `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe` | 可执行、可 import compiled backend | CPython 3.12.9, AMD64 | NumPy 2.5.1、SciPy 1.18.0、PyTorch 2.11.0+cu128；Numba 不可 import |
| `C:\Users\Jing_\AppData\Local\Microsoft\WindowsApps\python.exe` | 排除 | 0 字节 WindowsApps 占位文件 | 不作为解释器 |
| `E:\GNSS_Multipath_Project\.venv` / `venv` / `env` | 未发现 | — | 项目附近没有可用虚拟环境 |

已检查用户 uv 相关目录；未发现可直接调用的其他 Python 解释器或项目 venv。没有把其他项目的环境复制进 GNSS 项目。

## 推荐候选环境 receipt

### Python

- 绝对路径：`D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe`
- Python：`3.12.9 (MSC v.1942 64 bit AMD64)`
- 平台：Windows 11，AMD64
- Python executable SHA-256：

  `3638cd6a1236660910fe5e278994d309c073fb4bb49ee061f48bd4ccaaa0a191`

- `pyvenv.cfg` SHA-256：

  `ead81cc880a84152be74bdacea69a0102641118905934bcaea98c4e1478afdf7`

### 已安装包

- NumPy：`2.5.1`
- SciPy：`1.18.0`
- PyTorch：`2.11.0+cu128`
- Numba：不可 import
- pyFFTW：不可 import

路径均位于候选 venv 自身：

- `D:\Research\ChannelModeling-Agent\.venv\Lib\site-packages\numpy`
- `D:\Research\ChannelModeling-Agent\.venv\Lib\site-packages\scipy`
- `D:\Research\ChannelModeling-Agent\.venv\Lib\site-packages\torch`

### BLAS/backend

NumPy `show_config()` 报告：

- BLAS/LAPACK：`scipy-openblas`
- OpenBLAS：`0.3.33.112.0`
- `USE64BITINT`
- `DYNAMIC_ARCH`
- CPU 最大线程报告为 24
- SIMD baseline：x86_v2
- detected：x86_v3

NumPy/SciPy 的构建信息显示为已编译的 Windows AMD64 数值路径；本审计没有修改其配置。

PyTorch 只作为候选比较记录：

- CPU tensor/FFT 可调用
- MKLDNN 可用
- CUDA 可用，但本项目 raw-coarse 后续不应默认依赖 CUDA 或 GPU

## 固定 microbenchmark

测试脚本仍为：

`E:\GNSS_Multipath_Project\scripts\sage_pipeline\run_batch_sampling_raw_coarse_v1_2_v2.py`

任务固定为 G16 Stage0 catalog 的位置：

```text
[0, 743, 1486, 2228]
```

该子集按 catalog 位置确定，未读取 Stage3/Stage4 事件位置，不用于调参。

当前标准库 fallback 与候选 NumPy backend 的同规模结果：

| 指标 | 标准库 fallback | NumPy candidate |
|---|---:|---:|
| old kernel wall-clock | 约 0.141–0.143 s | 约 0.143 s（同一 Python kernel调用） |
| new kernel wall-clock | 约 0.145 s | 0.0855 s |
| new 相对 old speedup | 约 0.98× | 1.67× |
| score/delay 数值一致性 | PASS（此前 smoke） | FAIL |

候选 NumPy microbenchmark 记录：

- old kernel：`0.1426936 s`
- new kernel：`0.0854893 s`
- wall-clock speedup：`1.6691×`
- 比较记录数：12
- mismatch：6
- 最大 score 差：约 `3.3734 dB`
- delay separation：至少一项不一致
- 目标 score tolerance：`1e-8`
- 目标 delay tolerance：`0 sample`
- peak-ratio tolerance：`1e-8 dB`
- Doppler tolerance：`1e-8 Hz`

因此，虽然 NumPy kernel 在这组小样本上显示出约 1.67× 的 wall-clock 优势，但它没有通过科学数值等价门禁。速度不能抵消 score/peak selection 语义改变的风险。

## mismatch 现象

6 个不一致主要出现在 B1 和部分 D100 比较：

- B1 某些窗口 score 差约 1.76–3.37 dB。
- 一项 B1 delay separation 从 3 变为 2。
- 一项 B2-D100 delay separation 从 4 变为 2。
- B2-D200 在本次固定子集上 score 没有差异，但不能据此证明全量等价。

当前证据只能说明 NumPy batch 实现与 legacy reference 的 block/Doppler/peak 组合语义尚未完全对齐。不能在没有进一步定位前断言具体是 B1 20 ms 合并、相位索引、Doppler 选择或 peak tie-break 中哪一个单独导致差异。

## 当前 v2 preflight 状态

项目默认 Python 环境的 v2 preflight receipt 已记录：

`dataset_generation_logs/sampling_validation/batch_sampled_v1_2_prototype_v2_retry/preflight.json`

默认环境：

- NumPy 不可用
- 正式 Phase A 安全阻止
- G16/G25 未执行
- G11 未执行

使用候选 venv 直接 import v2 并调用 `_preflight()` 时，preflight 本身为可通过状态；但随后 microbenchmark 数值门禁失败。因此候选环境只能作为后续修复 kernel 的审计环境，不能作为当前生产执行环境。

## backend 排序

### 1. NumPy/SciPy candidate venv — 最推荐的修复目标，但当前不可放行

理由：

- 与 v2 的矩阵化复数乘法、FFT/correlation 设计最接近。
- 已存在且可直接 import。
- 有明确 Python/venv/package 路径和 hash receipt。
- OpenBLAS/AMD64 compiled backend 可审计。

限制：

- venv 属于 `ChannelModeling-Agent`，不是 GNSS 项目独立环境。
- 当前 NumPy kernel 数值一致性 FAIL。
- 不应直接把该解释器交给正式 wrapper 执行，直到新 kernel 通过完整门禁。

### 2. PyTorch CPU — 备选，不建议当前采用

它可以使用 CPU tensor、FFT 和 MKLDNN，但安装包带 CUDA 依赖，环境更重，与当前 v2 的 NumPy 数据结构和测试距离更远；本审计没有把 PyTorch kernel 作为正式替代实现，也没有执行 raw-coarse production benchmark。

### 3. 默认用户 Python 标准库 fallback — 不推荐

它稳定且隔离，但没有 compiled numeric backend。此前 G16 标准库 raw-coarse 记录为 18,806.16 s，约为历史 full Stage1 3,900 s 的 4.82×，不符合性能目标。

## 后续环境 proposal（仅设计，不执行）

推荐未来由显式路径调用候选解释器，而不是修改 PATH：

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' `
  'E:\GNSS_Multipath_Project\scripts\sage_pipeline\run_batch_sampling_raw_coarse_v1_2_v2.py' `
  --project-root 'E:\GNSS_Multipath_Project' `
  --output-root 'E:\GNSS_Multipath_Project\dataset_generation_logs\sampling_validation\<new-v2-namespace>'
```

正式使用前必须：

1. 修复 NumPy B1/B2 kernel，使 score、delay、Doppler 和 peak tie-break 在规定容差内与 reference 等价。
2. 重新生成新的 parameter hash 和全新 output namespace。
3. 将 Python executable、venv cfg、NumPy/SciPy 版本、BLAS 信息和 hash 写入 execution receipt。
4. 仍由 preflight 确认未调用 MATLAB/SAGE、输出 namespace 为空、`gold_labels_used_for_selection=false`。
5. 不把任何 site-packages 或 DLL 复制到 GNSS 项目，也不修改其他项目。

## 最终门禁

当前不能执行正式 G16/G25 Phase A，原因不是“没有 backend”，而是“现有 compiled backend 尚未通过数值一致性”。因此：

- 不运行 G16/G25 正式 raw pass。
- 不运行 G11。
- 不恢复 Wave-2A full-scan。
- 不处理 20.46 MHz。
- 不生成 execution request。

## 唯一建议

在保持 `D:\Research\ChannelModeling-Agent\.venv` 只读的前提下，先修复并重新验证 v2 NumPy kernel 的 B1/B2 数值一致性；只有在 score、delay、Doppler/peak 选择全部通过既定容差后，才使用该显式 Python 路径重新进行 G16→G25 Phase A。不要在当前 mismatch 状态下运行正式 raw-coarse。
