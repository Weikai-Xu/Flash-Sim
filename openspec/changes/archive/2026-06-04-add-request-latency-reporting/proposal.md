## Why

当前事件驱动仿真器能够完成请求执行、时间线记录和日志输出，但缺少面向单条输入 trace 请求的结构化延时统计结果。项目需要在仿真结束时直接得到“每条 req 的总时延及分阶段时延拆分”，以支持论文图表、结果分析和后续与真实 trace 的对照验证，因此需要把已有的请求流、PCIe 传输、地址转换和阵列执行阶段统一汇聚为可落盘的 JSON 报告。

## What Changes

- 新增请求级延时统计模块，在一次事件驱动仿真结束后为每条输入 `Request` 生成一条结构化记录，并输出到 `report/` 目录。
- 为每条请求统计总时延，以及以下 breakdown 延时：
  - Host 提交路径延时：在 Host SQ 中等待的时间，以及 `REQ_INIT` 事件被执行到请求真正经 PCIe 发出的时间。
  - PCIe 传输延时：Host 到 Device 的请求/数据传输、Device 到 Host 的完成/结果返回传输，均需按消息类型和负载大小计入。
  - AMU 地址转换延时：因读取 mapping page 而导致的额外等待时间。
  - TSU 调度等待延时：事务进入 TSU 后到首次被送入 PHY 之前的等待时间。
  - 阵列执行延时：细分为命令/地址发送、数据发送、芯片内部 flash 阵列操作、数据返回几个阶段。
- 扩展运行时和记录器，使请求、消息和事务在不改变核心调度语义的前提下暴露统计所需的阶段时间戳。
- 为报告 JSON 定义稳定的输出格式，保证每条请求都带有请求标识、类型、输入地址范围、状态、总时延和 breakdown 字段。
- 在 `tests/` 中新增覆盖 Host/PCIe/AMU/TSU/PHY 阶段聚合逻辑和端到端报告落盘的回归测试，形成闭环。

## Capabilities

### New Capabilities
- `request-latency-reporting`: 定义请求级总时延与分阶段延时的采集、聚合和 JSON 导出契约。

### Modified Capabilities
- `event-driven-simulation-runtime`: 仿真结束语义需要扩展为在事件队列清空后同步生成请求级统计报告。
- `host-device-request-flow`: Host、PCIe、HIL/AMU、TSU 与 PHY 请求流需要保留足够的阶段边界信息，以支持稳定的延时拆分统计。
- `simulator-tooling`: 事件驱动入口和报告导出工具行为将增加 `report/` 目录下的请求级 JSON 产物。

## Impact

- 代码范围：
  - `flash_sim/common.py` 中 `Request` / `Transaction` 相关元数据结构
  - `flash_sim/Host.py`
  - `flash_sim/pcie_link.py`
  - `flash_sim/HIL.py`
  - `flash_sim/FTL.py`
  - `flash_sim/PHY.py`
  - `flash_sim/engine.py`
  - 可能新增独立统计模块，如 `flash_sim/request_latency_report.py`
- 输出影响：新增 `report/*.json` 结果文件，不替代现有 `output/*.log`。
- 测试影响：需要新增请求级统计单元测试与端到端报告生成测试。
- 主要测试目标：给定包含 `write -> read` 或 `read` 触发 mapping miss 的 trace，报告中必须出现对应请求的总时延与 breakdown，并且 breakdown 求和与总时延保持一致或具备明确的残差规则。

## Non-goals

- 不在本次变更中引入新的性能优化策略，也不改变 Host、TSU、GC/WL 或 PHY 的调度算法本身。
- 不要求在本次变更中提供 HTML 可视化、聚合统计图表或 CLI 子命令扩展，重点仅限于仿真结束后的 JSON 报告导出。
- 不将范围扩展到 standalone `FlashSimulator` 路径；本次仅覆盖事件驱动引擎与 `flash_sim/main.py` 所走的请求流。
- 不尝试在本次变更中修复与本需求无关的既有端到端脚本行为差异。
