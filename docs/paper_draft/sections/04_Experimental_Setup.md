# 4 Experimental Setup

本章介绍GNSS多径路径提取实验所采用的射频采集系统、动态测量数据集、GNSS-SDR预处理流程、卫星导航与几何信息来源，以及后续SAGE处理的实验配置。本文关注的是车辆运动条件下的GNSS传播信道变化；车辆本身仅作为天线的动态安装平台，不作为研究对象进行车型或车辆属性分析。

## 4.1 GNSS measurement system

The measurement antenna is a GNSS dome antenna mounted on the vehicle roof.

实验采用TEST-TREE RF-Catcher V2作为射频信号采集与回放设备。根据设备手册，RF-Catcher属于射频信号捕获与回放设备，用于保存后续离线处理所需的GNSS中频/基带采样数据。

测量信号为GPS L1 C/A，中心频率为1575.42 MHz。GNSS天线为车顶安装的dome antenna，采用右旋圆极化（RHCP），有源增益为40 dB。天线安装在车辆车顶，使接收机能够在真实道路运动过程中获得随时间变化的卫星可见性、遮挡和反射条件。车辆在本研究中只提供天线的动态运动，不引入车型、品牌等与传播参数无关的研究变量。

原始采样数据以交错I/Q形式保存，数据类型为little-endian int16。对于当前论文数据生产主线，采样率为10.23 MHz；项目中另有20.46 MHz记录，但该采样率尚未完成与当前SAGE生产配置相同的适配和验证，因此不纳入当前正式production结论。

## 4.2 Dataset and dynamic measurement scenarios

项目数据集包含19个scene，其中13个scene的采样率为10.23 MHz，6个scene的采样率为20.46 MHz。10.23 MHz数据覆盖Urban、Mountain/Valley、Highway/Open和Special Reflective等人工确认的环境类别，并进一步记录道路类型、车辆速度和特殊环境描述。

当前论文数据生产聚焦于13个10.23 MHz measurement scenes。每个scene保留独立的raw IQ路径、GNSS-SDR解析结果、标准化导航文件、trajectory文件和satellite geometry文件，并以scene-PRN为基本生产任务。环境字段来自采集后的人工测量描述，而不是由SAGE结果或文件名自动推断。

动态测量中的车辆运动使天线位置、传播路径和遮挡关系随时间变化，从而形成时变GNSS多径观测。本文将这些变化作为传播信道建模的输入条件，而不把车辆属性本身作为解释变量。每个scene的具体环境标签和数据路径由项目中的scene metadata layer统一管理。

## 4.3 GNSS-SDR preprocessing

The configuration template records `sampling_frequency=10230000` Hz for the 10.23 MHz processing chain.

原始GNSS IQ首先由GNSS-SDR进行信号跟踪、导航信息解码和辅助观测生成。当前项目使用GNSS-SDR v0.0.21及既有配置模板。预处理链可概括为：

```text
raw interleaved I/Q
        -> GNSS-SDR acquisition and tracking
        -> tracking / telemetry / observables / PVT
        -> RINEX NAV/OBS and NMEA
        -> NAV-aided SAGE input preparation
```

GNSS-SDR输入配置使用`item_type=ishort`，对应本实验的int16采样格式；采样频率设置为10230000 Hz，并采用GPS_L1_CA acquisition。跟踪部分使用GPS_L1_CA_DLL_PLL配置，其中PLL带宽为40 Hz，DLL带宽为4 Hz，early-late间隔为0.5 chip。GNSS-SDR同时运行telemetry decoder，并生成observables、RTKLIB PVT、RINEX和NMEA输出。

tracking结果提供每个跟踪通道的sample counter、载波Doppler、code frequency、C/N0、carrier lock和TOW等字段。telemetry结果提供导航符号、PRN、TOW和对应采样位置。上述信息用于建立PRN-specific NAV symbol catalog、检查连续性并构造后续40 ms观测窗口。

标准化的RINEX NAV/OBS、trajectory NMEA以及satellite geometry文件被整理到每个scene的独立目录中。RINEX NAV和trajectory既是输入完整性检查的一部分，也是后续导航和几何provenance的可追溯来源；SAGE的直接窗口计算主要使用与目标PRN和tracking channel对应的tracking、telemetry及原始IQ数据。

## 4.4 Satellite navigation and geometry information

导航和卫星几何信息由多个相互关联但职责不同的文件来源提供。RINEX NAV用于导航文件provenance以及GPS PRN过滤；它不在当前geometry生成流程中被用于重新计算广播星历卫星位置。trajectory来自GNSS-SDR生成的NMEA文件，其中RMC记录可提供车辆速度信息，并用于当前Pipeline中的相对Doppler范围估计。

当前satellite geometry产品主要基于NMEA GSV记录生成，用于整理卫星观测时间、仰角和方位角等几何信息。geometry生成过程同时读取RINEX NAV以完成GPS PRN过滤，但其算法配置明确关闭了broadcast ephemeris position recomputation。因此，本文对卫星几何的描述应表述为NMEA GSV-based geometry，而不能表述为基于RINEX NAV重新传播星历得到的卫星位置。

后续统计分析计划将仰角划分为LOW（0--30°）、MID（30--60°）和HIGH（60--90°）三个候选区间。该分区是后续环境条件化信道建模的分析设计，不代表当前已经完成了全部window-level几何关联或统计模型。geometry时间戳与SAGE 40 ms窗口之间的精确对齐仍需独立QA确认。

## 4.5 SAGE experimental configuration

在GNSS-SDR预处理的基础上，本文采用Pipeline V3执行NAV-aided SAGE路径提取。该Pipeline以一个scene、一个PRN和一个显式指定的tracking channel为基本运行单元，并保持10.23 MHz的已验证配置。

Pipeline采用Stage0--Stage4的层级证据框架：

1. **Stage0：NAV symbol alignment and valid-window construction。** 根据telemetry和tracking信息建立连续导航符号目录，并构造完整的40 ms观测窗口。该阶段只定义可分析窗口，不作多径判定。
2. **Stage1：correlation-based candidate screening。** 对有效40 ms窗口执行NAV wipe和相关搜索，获得候选窗口。候选窗口仅表示需要进一步拟合的对象，不等同于多径。
3. **Stage2：fractional-delay and Doppler SAGE estimation。** 对Stage1候选窗口评估模型阶数`L=1,2,3,4`，估计路径的delay、Doppler、amplitude、phase及相对功率等参数。`L>=2`表示高阶模型被选择，不能单独解释为confirmed multipath。
4. **Stage3：temporal persistence validation。** 在相邻40 ms窗口中检查路径delay连续性、Doppler一致性、功率稳定性和持续性，形成reliable center候选。Stage3 reliable center仍不是最终confirmed multipath。
5. **Stage4：multi-snapshot joint estimation。** 以中心窗口附近的五个20 ms snapshot组成约100 ms联合观测，在共同几何和多快照约束下进行joint estimation。当前项目的confirmed criterion为：`joint_valid=1`、`joint_multipath_count>0`，并且Stage4 path table中存在`is_multipath=1`的有效路径。

该层级设计将窗口可用性、候选相关性、高阶模型、时间持续性和联合路径确认区分开来，避免把单一阶段输出直接当作物理多径标签。最终confirmed path的路径级参数将作为后续PDP、delay spread、Doppler spread、Ricean K-factor以及其他候选信道统计特征的输入；相关数据库和统计模型目前尚未完成。

## 4.6 Production scope and reproducibility status

当前正式论文数据生产只使用10.23 MHz数据，并通过immutable manifest、输入provenance、hash、`new_only`输出保护、正常Windows用户执行链和独立post-run QA进行控制。已有正式production结果包括：

- `F1023_V70_D0117_P4/G11/ch2`：已完成full SAGE并通过独立QA；
- `F1023_V70_D0120_P1/G18/ch2`：已完成full SAGE并通过独立QA；
- `F1023_V70_D0120_P5/G16/ch1`：当前处于Running / execution in progress，尚未完成独立post-run QA。

上述状态只描述数据生产和执行验证进度，不代表完整event database、全部scene处理或最终统计信道模型已经完成。path database、channel parameter database以及LOW/MID/HIGH条件化统计建模仍属于后续工作。

需要特别说明的是，当前项目artifact没有记录完整的设备时间同步、外部时钟、采集触发或UTC对齐细节。除非补充原始采集记录，否则本文不对这些时间同步细节作具体技术断言；这也意味着后续window-level geometry alignment需要在数据生产和统计建模前单独完成QA。
