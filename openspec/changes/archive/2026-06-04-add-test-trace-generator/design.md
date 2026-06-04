## Context

当前仓库里的 engine trace 测试数据主要靠 `test_case/` 下的手写 JSON 文件维持，`flash_sim/trace_generation/` 里也只有一个面向 GC 的单用途脚本，尚未形成“读取 preconditioning 数据并按当前运行时拓扑自动生成综合 trace”的稳定入口。与此同时，event-driven 路径已经把几个关键约束固定下来：

- `pre_data/precondition_data.json` 保存的是 page 级 `lpa`、`valid_bitmap` 和页面数据，且 `Block_Manager.preconditioning(...)` 会把这些内容直接落到 `PHY._storage` 与初始映射结构里。
- engine trace 使用 sector 级 `start_lha` / `size` 表达 `read` / `write`，并使用 static 区间的 `start_lha` / `size` 表达 `search` / `compute`。
- `Address_Mapping_Unit` 已经内建“随机访问数据页”和“mapping 预留页”边界，`GC_WL_MANAGER_FREE_BLOCK_POOL_THRESHOLD`、`PlaneBKE.free_block_pool`、`write_frontier_block` 等结构也已经表达了真实的 GC 触发条件。

这意味着如果生成器自己重写一套几何换算和 GC 估算逻辑，很容易与运行时漂移；但如果完全只靠静态手写 trace，又无法稳妥覆盖“预置数据读取 + 写后读 + static 请求 + GC 压力”这次用户想要的组合场景。

## Goals / Non-Goals

**Goals:**
- 在 `test_script/` 下提供一个可重复执行的 trace 生成脚本，默认写出 `test_case/test_trace.json`。
- 让生成器从 `pre_data/precondition_data.json` 中挑选真实已预置到 flash 的数据，生成至少一部分直达 flash 的 `READ`。
- 让生成器额外构造至少一组“生成的 `WRITE` 之后再 `READ`”的链路，覆盖写入数据读取场景。
- 在同一份 trace 中包含 `READ`、`WRITE`、`SEARCH`、`COMPUTE` 四类主要请求，并保证地址域合法。
- 基于当前 runtime 几何配置和 preconditioning 后的真实 plane 状态，推导足以走到现有 GC 路径的写入压力，而不是硬编码固定写请求数。
- 将现有 `tests/` 目录重命名为 `test_script/`，并同步 pytest 配置与文档约定。

**Non-Goals:**
- 不修改 engine trace schema，也不引入新的请求类型或附加字段。
- 不修改 `Block_Manager.preconditioning(...)` 的输入格式与预置分布算法。
- 不改变 `GC_WL_Unit`、`TSU`、`PHY` 的调度、回收或介质执行语义。
- 不扩展为通用 fuzzing 平台，也不在本次变更中生成大量 benchmark 级 trace 变体。

## Decisions

### Decision 1: 生成脚本与回归脚本统一迁移到 `test_script/`

本次实现会把现有 `tests/` 目录整体重命名为 `test_script/`，并把新的 trace 生成脚本直接放在该目录下，而不是继续放在 `flash_sim/trace_generation/` 里。

理由：
- 这是用户显式提出的目录结果，最终形态应当是“测试脚本”和“测试数据生成脚本”同处一个根目录。
- 生成器主要服务回归测试，不是 runtime 模块的一部分；放进 `flash_sim/` 容易让它看起来像产品代码路径。
- pytest 已通过 `pyproject.toml` 的 `testpaths` 显式指向 `tests`，重命名后只需要一次性更新配置和文档，不需要引入额外的兼容层。

备选方案：
- 保持 `tests/` 不动，只把新脚本单独放到 `flash_sim/trace_generation/`。好处是迁移小；缺点是与用户要求不符，且测试辅助工具继续分散。
- 仅新增 `test_script/`，保留 `tests/` 作为旧目录。好处是平滑；缺点是双目录并存会让后续约定变得模糊。

### Decision 2: 生成器直接复用真实的 `Block_Manager` / `PHY` / `Address_Mapping_Unit` 预置流程

生成脚本会像 `tests/test_preconditioning.py` 那样，在内存中构造最小运行时夹具，执行一次 `Block_Manager.preconditioning(...)`，再从生成后的 `PlaneBKE`、`PHY._storage` 和 `Address_Mapping_Unit` 状态反推地址池与 GC 压力。

理由：
- 这样可以复用真实的拓扑、mapping 预留区边界、write frontier 和 free block bookkeeping，避免脚本手搓一套容易漂移的估算逻辑。
- `precondition_data.json` 里的 `lpa` 是 page 级，真实运行时才知道哪些页属于随机访问区、哪些页会因为 mapping 预留区而不可直接分配。
- 用户要求“根据当前的 flash 阵列配置”自适应，直接复用运行时对象比复制常量更可靠。

备选方案：
- 只根据 `common.py` / `config.py` 常量做静态换算。实现简单，但容易忽略 mapping tail、write frontier 剩余页和 preconditioning 后实际 plane 分布。
- 直接启动完整 `Engine` 来探测状态。精确但太重，也会混入事件队列、副作用日志和与生成任务无关的依赖。

### Decision 3: 把待生成请求拆成四类 recipe，再统一编排

生成器不会边遍历边随手写请求，而是先构造四类 recipe：

- `precondition_read_recipes`：从 `precondition_data.json` 中选出若干 page 记录，根据 `valid_bitmap` 折算出 sector 级 `read`。
- `write_readback_recipes`：先生成随机访问 `write`，再绑定一个后继 `read`，用于覆盖写后读。
- `static_recipes`：在 static 区内分别生成至少一个 `search` 和 `compute`。
- `gc_pressure_write_recipes`：针对目标 plane 追加写入压力，用于把 free block pool 压到 GC 阈值附近并触发现有回收路径。

理由：
- 用户的五条要求本质上来自不同语义来源：有的依赖 preconditioning，有的依赖写后关系，有的依赖 static 区，有的依赖 GC bookkeeping。先拆 recipe 再编排更容易保证每类目标都达成。
- 这样也方便后续测试对生成结果做结构化断言，例如“至少一个 precondition-backed read”“至少一个 dependent read-back”“至少一组 static 请求”。

备选方案：
- 使用单一随机循环逐步决定下一条请求。好处是代码看起来更随机；缺点是很难在不反复回溯的情况下同时满足所有强约束。

### Decision 4: precondition-backed `READ` 以 page 记录为源，但输出 sector 级地址范围

`precondition_data.json` 的主键是 page 级 `lpa`，而 engine trace 的 `read` 请求使用 sector 级 `start_lha` / `size`。因此生成器会：

1. 从 precondition 记录中找出 `valid_bitmap` 中连续或可采样的有效 sector 段。
2. 把 page 级 `lpa` 转换为 sector 级起点：`start_lha = lpa * SECTOR_PER_PAGE + sector_offset`。
3. 使用不超过页面有效范围的 `size` 生成 `read` 请求。

理由：
- 这能确保请求真正落在 preconditioning 已写入的 flash 数据上，而不是只“碰巧访问到同一个 page 编号”。
- 保留 sector 级粒度后，生成器也可以构造部分页读取，而不必全页读取。

备选方案：
- 所有 precondition 读取都按整页 `size = SECTOR_PER_PAGE` 生成。实现简单，但对 `valid_bitmap` 的利用较粗糙，也更难控制和其他请求交错时的体量。

### Decision 5: GC 压力通过“选择目标 plane + 计算额外块消耗”来推导，而不是固定写条数

生成器会先扫描 preconditioning 后的 random-access planes，优先选择同时满足以下条件的目标 plane：

- `invalid_page_count > 0`，确保现有 GC 路径存在可选 victim；
- 距离 `GC_WL_MANAGER_FREE_BLOCK_POOL_THRESHOLD` 最近，即额外需要消耗的 free block 最少；
- 若存在并列，优先选择已经有较多有效数据、写前沿剩余页较少的 plane。

随后，生成器会根据该 plane 的：

- `len(free_block_pool)`
- `write_frontier_block` 当前剩余页数
- 当前已映射的可覆盖 LPA 集合

推导需要追加多少个落在同一 plane 的随机访问 `write`，才能让该 plane 进入 `free_block_pool <= threshold` 的状态。如果找不到带现成 invalid page 的 plane，则生成器会先对同一 plane 上的已映射地址做覆盖写，主动制造 invalid page，再继续追加压力写。

理由：
- 单纯“写很多”并不等价于“能触发 GC 操作”；如果没有 invalid page，阈值到了也可能无 victim 可回收。
- 真实运行时先消耗 write frontier 剩余页，再首次触碰新 block 才会从 `free_block_pool` 中拿走一个 block；这个细节只有基于真实 plane state 才能算对。

备选方案：
- 沿用 `gen_gc_test.py` 那种固定写满若干 block 的办法。适合空盘场景，但对 preconditioning 后的真实状态不稳定。
- 只校验“理论上会触发 `check_gc()`”，不保证可进入实际 GC 路径。无法满足用户“写操作生成的数量可以触发 GC 操作”的意图。

### Decision 6: 通过“约束随机调度器”实现交错，而不是完全自由 shuffle

为了同时满足“尽量随机交错”和“不能打乱依赖顺序”，生成器会把 recipe 先放入带依赖信息的待调度池，再用带 seed 的随机选择器逐步出队：

- `write -> read` 这类依赖对在前驱未发出前不可选。
- 当存在多个依赖已满足的请求族时，调度器优先选择与上一条不同的请求类型。
- 只有当当前池中只剩单一类型或依赖限制使其他类型不可选时，才允许连续发出同类型请求。

理由：
- 纯 `random.shuffle(...)` 很容易把同类型请求重新团成块，也容易把读回请求排到写前面。
- 显式约束后的随机调度既保留随机性，又能形成可测试的“避免无意义聚集”规则。

备选方案：
- 先按类型分桶，再固定轮转拼接。顺序过于机械，不够随机。
- 完全自由 shuffle 后再做修补。实现更绕，而且修补次数不可控。

### Decision 7: 新脚本提供少量显式参数，并默认生成稳定仓库夹具

脚本会保留少量但明确的 CLI 参数，例如：

- `--seed`
- `--output`
- `--pre-data`
- `--request-budget` 或等价的目标规模参数

默认情况下不要求用户提供这些参数，直接生成仓库标准夹具 `test_case/test_trace.json`。

理由：
- 回归测试需要默认路径，便于仓库内直接调用。
- 研究和调试时又需要固定种子与可扩展规模，否则“随机交错”会让问题难以复现。

备选方案：
- 完全无参数。最简单，但一旦要复现实例或临时输出到其他文件会很受限。
- 暴露大量调参开关。灵活但会显著增加维护成本，也超出本次需求。

## Design Rationale

这次设计的核心取舍是：不要把生成器做成“脱离模拟器语义的随机 JSON 拼接器”，而要把它做成“贴着当前 runtime 真实状态生成测试夹具的工具”。因此几个关键决定都围绕“复用真实状态”展开：precondition-backed `READ` 直接来自 `precondition_data.json` 的有效 sector，GC 压力直接来自 preconditioning 后的 plane bookkeeping，地址合法性直接受现有随机访问区和 static 区边界约束。与此同时，用户明确要求请求类型尽量交错，所以我们没有选择最容易实现的“按阶段拼接 trace”，而是引入了受依赖约束的随机调度器，在保住 `write -> read` 因果关系的同时尽量打散类型聚集。最终得到的是一套面向回归测试的稳定生成流程，而不是一份偶然可用的样例数据。

## Risks / Trade-offs

- [目录重命名会影响 pytest 发现路径和文档命令] → 同步修改 `pyproject.toml` 的 `testpaths`、README 中的执行示例，以及所有显式引用 `tests/` 的仓库文本。
- [生成器复用真实 preconditioning 夹具会增加脚本启动成本] → 仅在脚本启动阶段构造一次最小对象并执行一次预置；不启动完整事件引擎。
- [目标 plane 选择过于依赖当前 precondition 分布，可能让 GC 场景不稳定] → 优先选择已有 invalid page 且阈值距离最小的 plane；若不存在，则显式生成覆盖写来制造 invalid page。
- [随机交错规则如果太宽松，仍可能出现局部聚集] → 把“有可选不同类型时优先切换类型”写成实现约束和测试断言，而不是只依赖概率。
- [现有测试脚本迁移到 `test_script/` 后，个别相对路径可能失效] → 保留目录内部相对结构，并逐个修正基于 `__file__` 的路径推导与任何硬编码的 `tests/` 文本。

## Migration Plan

1. 将 `tests/` 重命名为 `test_script/`，更新 `pyproject.toml`、README 与仓库内所有显式 `tests/` 引用。
2. 在 `test_script/` 下新增 trace 生成脚本，提供默认输出路径和可复现 seed。
3. 在脚本中实现最小 preconditioning 夹具构造、地址池提取、目标 plane 选择和 GC 压力估算。
4. 实现受依赖约束的随机调度器，输出包含 `READ/WRITE/SEARCH/COMPUTE` 的最终 trace。
5. 新增针对生成脚本的测试，验证默认输出、四类请求齐全、precondition-backed read、write-readback、static 地址合法性和 GC 压力推导。
6. 运行重命名后的 pytest 命令与生成脚本本身，确认 `test_case/test_trace.json` 可稳定生成。

回滚策略：
- 若目录迁移引发广泛测试发现问题，可先保留变更分支内的 OpenSpec 提案，不合并实现；一旦实现已经开始，回滚时优先恢复 `pyproject.toml` 的 `testpaths` 与目录名称，再撤回生成脚本入口。

## Open Questions

- 生成脚本是否需要把“选中的目标 plane、估算出的 GC 压力写入数、命中的 precondition LPA”额外输出为调试摘要，还是只写 trace JSON 即可。
- `request-budget` 是否应以“总请求数”为单位，还是以“每类请求最小配额 + GC 压力附加量”为单位暴露给用户。
- 是否需要在首版测试里真正驱动一次事件引擎运行，证明新生成的 `test_trace.json` 不仅结构合法，而且确实能在回归路径上触发期望的 GC 行为。
