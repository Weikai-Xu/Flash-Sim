## Why

当前仓库里的 `test_case/test_trace.json` 仍是手写样例，无法稳定覆盖预置数据读取、控制器缓存回读、`READ/WRITE/SEARCH/COMPUTE` 交错执行，以及写入压力触发 GC 这些更接近真实回归场景的路径。现在补上一个基于 `pre_data/precondition_data.json` 和当前 flash 几何配置自动生成 trace 的脚本，可以把测试数据从一次性样例升级为可复现、可扩展、能随拓扑自动适配的测试夹具。

## What Changes

- 新增一个专门的 trace 生成能力，在仓库内自动生成 `test_case/test_trace.json`，而不是继续手工维护单一静态文件。
- 生成脚本迁移到新的 `test_script/` 目录，并将当前 `tests/` 目录整体重命名为 `test_script/`，统一“测试脚本”和“生成脚本”所在位置。
- 生成逻辑会读取 `pre_data/precondition_data.json`，挑选部分已预置到 flash 中的随机访问地址，保证生成的 `READ` 请求包含对 preconditioning 阶段已写入数据的访问。
- 生成逻辑会在同一份 trace 中包含 `READ`、`WRITE`、`SEARCH`、`COMPUTE` 四类主请求，并尽量随机交错，避免同类请求大段聚集。
- 生成逻辑会显式包含“先写后读”或“写入后命中缓存/落盘后再读”的读写链路，确保 trace 不只是独立的读和写样本拼接。
- 生成逻辑会基于当前 flash 阵列配置、`GC_WL_MANAGER_FREE_BLOCK_POOL_THRESHOLD`、每 plane 可写页数和预置占用情况，追加足够多的随机访问 `WRITE`，使 trace 具备触发 GC 的写入压力。
- 生成脚本会暴露有限但明确的参数，例如随机种子、输出路径和目标请求规模，保证回归测试既可复现又可按需扩展。

## Capabilities

### New Capabilities
- `trace-test-data-generation`: 定义基于当前 event-driven runtime 几何配置与 preconditioning 数据自动生成 engine trace 测试数据、输出目标文件与目录约定的能力。

### Modified Capabilities
- None.

## Impact

- 代码范围：
  - 新增 `test_script/` 下的 trace 生成脚本。
  - `tests/` 目录将重命名为 `test_script/`，因此受影响的测试入口、导入路径、文档说明和可能的命令示例都需要同步调整。
  - 生成脚本会读取 `pre_data/precondition_data.json`，并依赖 `flash_sim/common.py`、`flash_sim/config.py`、必要时 `flash_sim/FTL.py` 中的拓扑和 GC 相关常量或辅助函数。
- 明确在 scope 内的模块与函数：
  - `pre_data/precondition_data.json` 的消费方式。
  - `flash_sim/common.py` / `flash_sim/config.py` 中与 event runtime 几何、static 区域边界、GC 阈值相关的公开常量。
  - 仓库内测试脚本目录结构以及 `test_case/test_trace.json` 的生成流程。
- 明确不在本次 scope 内的内容：
  - 不修改 event-driven engine 的 trace schema，不新增请求类型。
  - 不修改 `Block_Manager.preconditioning(...)` 的数据格式或预置策略。
  - 不改变 `GC_WL_Unit`、`TSU`、`PHY` 的运行时调度与 GC 算法本身；本次只保证生成的数据能触发既有 GC 路径。
  - 不重构 standalone simulator 或 CLI 子命令。
- 主要测试目标：
  - 生成一份 trace 后，应至少能验证其中存在对 preconditioned LHA 的 `READ`、存在 `READ/WRITE/SEARCH/COMPUTE` 四类请求、且写入数量足以把至少一个 random-access plane 的 free block pool 压到 GC 阈值以下。

## Non-goals

- 不追求构建一个通用 trace fuzzing 框架；本次只提供面向仓库回归测试的受控生成器。
- 不要求自动生成多份不同主题的测试集或批量 benchmark 数据。
- 不在本次变更中引入新的测试运行器、pytest 插件或 CI pipeline 改造。
