# 仿真结果和验证报告

## 测试用例及结果

截至当前版本，仿真器已经建立了由 `test_case/` 与 `tests/` 共同组成的双层验证体系。`test_case/` 目录包含 15 个 JSON 轨迹场景，用于驱动请求回放与事件执行，覆盖普通读写、写后读、连续写、搜索与计算、未映射读、非法扇区读、非法域请求以及 GC 触发等典型输入模式。从输入分布看，这些场景累计包含 14 个写请求、8 个读请求、4 个 `SEARCH` 请求和 4 个 `COMPUTE` 请求，能够较好地覆盖主机侧可见操作以及若干异常路径。

`tests/` 目录当前包含 12 个自动化测试脚本，`pytest` 共可收集 154 项测试。测试内容覆盖了闪存时序模型、配置与三维几何参数、地址结构、Trace 解析与结果格式化、模拟器执行流程、总时延统计、PCIe 链路时延、数据缓存、预处理、异常请求处理、请求载荷兼容性，以及 GC 与磨损均衡控制等核心功能。其中，新增的 `tests/test_gc_wl_unit.py` 已对 `GC_WL_Unit` 命名替换、动态 wear leveling 的低磨损空闲块选择、安全块过滤规则、静态 wear leveling 触发与 barrier 保护机制进行了专门回归验证。

在当前代码状态下执行 `python -m pytest -q`，测试框架共收集 154 项用例，其中 153 项通过、1 项失败，总体通过率约为 99.35%。失败项为 `tests/test_read_write_trace.py::test_main_trace_read_after_write_completes_without_mapping_error`。从执行日志分析，当前 `flash_sim/main.py` 默认加载的是 `test_case/gc_test.json`，实际运行内容为两条 `WRITE` 请求，而该回归用例仍要求输出中出现 `RequestType.READ`。因此，这一失败更接近测试脚本预期与主程序默认输入配置之间的不一致，而不是地址映射、事务调度或完成回调链路中出现未捕获的功能性异常。除该项外，配置、时序、解析、缓存、预处理、异常传播以及 GC/WL 控制相关用例均已通过。

## 测试覆盖面分析

从功能维度看，现有测试已经覆盖仿真器的主要核心路径。`test_config.py` 与 `test_chip.py` 重点验证了 `FlashTiming`、`FlashGeometry`、`FlashAddress` 以及 SLC/MLC/TLC 时延模型的参数合法性与边界行为；`test_simulator.py`、`test_parser.py`、`test_request_payload_schema.py` 与 `test_request_error_handling.py` 覆盖了请求解析、输入兼容性、结果汇总、错误返回和模拟器主流程；`test_data_cache.py`、`test_preconditioning.py`、`test_pcie_link_latency.py` 则对缓存回写、预处理映射构建以及链路传输延迟进行了验证；`test_gc_wl_unit.py` 和 `test_invalid_request_errors_trace.py` 补充了 GC/WL 维护逻辑与端到端异常场景的定向回归。总体上，现有测试已经覆盖了“输入解析 - 地址映射 - 事务执行 - 完成返回”这一主链路，以及磨损均衡和错误处理等关键分支。

从代码覆盖率看，在暂时排除上述 1 个已知端到端回归用例的条件下，执行 `python -m pytest --cov=flash_sim --cov-report=term --ignore=tests/test_read_write_trace.py -q`，`flash_sim` 包的总体语句覆盖率约为 56%。其中，`simulator.py`、`Device.py`、`chip.py`、`pcie_link.py`、`common.py`、`config.py` 和 `parser.py` 的覆盖率分别约为 90%、91%、88%、82%、80%、76% 和 75%，说明配置、时延计算、协议封装与基础模拟流程已经具备较好的自动化验证基础。与此同时，复杂状态机和控制逻辑仍存在补强空间，`FTL.py` 的覆盖率约为 58%，`PHY.py` 约为 48%，表明块管理、映射维护、事务依赖、GC/WL 迁移和物理层事件联动虽然已具备针对性用例，但对长序列交互、资源竞争与异常分支的覆盖仍不充分。

此外，`cli.py`、`main.py`、`timeline_recorder.py`、`visualizer.py` 以及 `generate_precondition_data.py` 等外围脚本和工具模块尚未纳入稳定的自动化回归流程，当前覆盖率较低甚至为零。这说明现阶段验证工作主要聚焦于内核功能正确性，而在命令行入口、日志落盘、结果可视化以及数据生成链路上，仍需补充集成测试与回归基线。当前唯一失败的 `test_read_write_trace.py` 也表明，端到端运行脚本与测试夹具之间的同步机制需要进一步规范化。

## 仿真准确性检验

当前阶段的验证重点主要集中在功能正确性、接口约束、异常处理和模块级状态一致性上，尚未完成面向真实工作负载的定量准确性检验。因此，现有结果能够说明仿真器已经具备较完整的代码实现，并在请求解析、地址映射、缓存管理、事务调度、GC 和 wear leveling 等方面建立了可重复的验证基础，但尚不能仅凭当前测试结果直接给出“与真实设备行为偏差”的统计结论。

后续将基于公开工作负载数据集 `MSR Cambridge Trace` 开展仿真准确性验证。具体而言，将首先完成真实访问轨迹向仿真输入格式的转换，并在统一配置条件下进行长时间、多阶段回放；随后统计不同读写比例、到达间隔、热点分布与地址局部性对总时延、排队时延、GC 触发频率、写放大和块磨损分布的影响；最后将仿真结果与公开文献、可获得的实验观测值或基线模型进行对照，以评估该仿真器在功能行为、时延趋势和磨损演化上的一致性。通过这一阶段的工作，可以进一步验证仿真器不仅能够通过功能测试，而且能够在真实数据驱动场景下提供具有工程参考价值的结果。
