## Context

当前事件驱动路径已经具备较完整的生命周期节点：`Engine` 负责 `REQ_INIT` 注册与事件推进，`Host` 管理 SQ / CQ 和数据请求，`PCIe_link` 串行化双向消息并计算字节级传输延时，`HIL` 负责请求切分和缓存交互，`AMU` 在 mapping miss 时生成 `MAPPING_READ`，`TSU` 负责排队与下发，`PHY` 已显式拆分命令发送、芯片内部执行和数据返回事件。仓库内还存在 `TimelineRecorder`，说明当前代码已经接受通过 runtime hook 记录阶段信息的实现方式。

本次变更是一个跨越 `Host`、`PCIe`、`HIL`、`FTL`、`PHY`、`Engine` 和工具层的横切需求。难点不在于“能否拿到某个时间戳”，而在于如何把这些时间戳稳定地归因到输入 trace 的每一条请求，并在存在缓存提前完成、mapping 依赖、并行事务、共享 flush 写回和重叠区间的情况下，生成一份可解释、可测试、可复算的统计报告。

## Goals / Non-Goals

**Goals:**
- 为事件驱动仿真中的每条输入请求生成稳定的请求级统计记录。
- 输出总时延与分阶段时延，并明确各阶段的统计口径。
- 使统计模块能够覆盖 Host SQ、PCIe、AMU mapping wait、TSU 等待、PHY 命令/数据/阵列执行等阶段。
- 在 `report/` 目录生成 JSON 报告，供后续分析和论文制图使用。
- 为异步写回路径保留足够的 lineage 信息，使报告能够区分主机完成视角和后端持久化视角。
- 在 `tests/` 中增加模块级和端到端回归，确保统计结果可验证。

**Non-Goals:**
- 不重写现有调度、映射、GC/WL 或 PHY 执行算法。
- 不在本次设计中引入新的可视化前端或图表导出格式。
- 不试图统一 standalone `FlashSimulator` 与事件驱动引擎的统计模型。
- 不把请求级统计扩展为全系统吞吐量、带宽或利用率聚合框架。

## Decisions

### Decision 1: 新增独立的请求级统计模块，而不是直接复用 `TimelineRecorder` 的导出结果

新增独立模块，例如 `flash_sim/request_latency_report.py`，实现 `RequestLatencyRecorder` 与 `RequestLatencyReportWriter`。该模块沿用 `TimelineRecorder` 的 attach/hook 思路，但输出契约以“请求级 breakdown”为中心，而不是通用时间线段列表。

理由：
- `TimelineRecorder` 当前以可视化为目标，记录的是“发生过哪些阶段”，并不处理阶段归类、重叠消解、请求总时延计算和异步写回 lineage。
- 直接在导出的 timeline JSON 上做二次离线分析会把统计规则分散到工具层，不利于测试闭环。
- 独立模块可以复用部分 hook 技术，但保持报告 schema 稳定，避免与 HTML 时间线演化相互耦合。

备选方案：
- 方案 A：完全复用 `TimelineRecorder` 并离线后处理。优点是少写 hook；缺点是无法自然处理写回 lineage、重叠 reconciliation 和测试断言。
- 方案 B：在各业务模块里直接写统计逻辑。优点是精确；缺点是侵入性过强，破坏现有模块边界。

### Decision 2: 为每条输入请求引入稳定的 trace 级标识，并把统计记录锚定到该标识

在 `Engine.Initialize_event_queue(...)` 创建 `Request` 时，为请求补充稳定标识，例如 `trace_index`、`trace_time` 和 `report_req_id`。后续统计、消息关联和事务 lineage 都以该标识为主，而不是使用 `id(req)` 作为唯一键。

理由：
- `id(req)` 只适合进程内临时可视化，不适合稳定 JSON 产物与测试断言。
- 统计文件需要可读、可定位、可与输入 trace 对照，`trace_index + request type + start_lha + size` 更适合外部消费。
- flush 生成的后台事务会脱离原始 `Request` 生命周期，仅靠对象引用不利于跨阶段归因。

备选方案：
- 继续使用 `id(req)`。实现最简单，但测试脆弱，报告不可复现。
- 根据 `(type, time, start_lha, size)` 现算 key。可读但在 trace 含重复请求时不稳定。

### Decision 3: 统计模块记录“阶段区间”而不是只记录单点时间戳

对每条请求维护按阶段分类的区间列表，而不是只有若干 start/end 时间戳。核心阶段包括：
- `host_sq_wait`
- `host_dispatch`
- `pcie_host_to_device`
- `pcie_device_to_host`
- `amu_mapping_wait`
- `tsu_queue_wait`
- `phy_cmd_addr`
- `phy_data_in`
- `phy_array_exec`
- `phy_data_out`

每个区间由 `start`, `end`, `source` 组成，其中 `source` 可标注来自哪条 PCIe 消息、哪笔事务或哪次 mapping read。

理由：
- 一个请求可能拆分成多笔事务，也可能产生多次 PCIe 消息，单点时间戳不足以表达。
- 请求内部事务可能并行，只有区间集合才能在后处理阶段做 merged duration、overlap 统计和调试回溯。
- 后续测试可以直接断言区间存在性与持续时间，而不仅是最终总和。

备选方案：
- 仅保存阶段开始/结束单点。适合简单串行请求，但对并行事务和多条消息不稳健。

### Decision 4: breakdown 采用“分阶段 merged duration + overlap/untracked reconciliation”模型

对于每条请求，报告中的每个 breakdown 字段表示该阶段所有区间合并后的总时长；另外增加两个 reconciliation 字段：
- `overlap_latency`: 各阶段 merged 时长求和后，因为跨阶段并行或共享区间导致超过总时延的部分。
- `untracked_latency`: 请求总时延中未被任何已知阶段区间覆盖的剩余时间。

由此满足以下恒等式：

`sum(base_stage_latencies) - overlap_latency + untracked_latency = total_latency`

理由：
- 一个请求的多笔事务可能并行进入 TSU/PHY，不同阶段之间可能在时间轴上重叠。
- 如果强行要求简单 breakdown 求和等于总时延，会掩盖并行执行事实，导致统计失真。
- 显式暴露 overlap / untracked 字段既保留了阶段含义，又保证报告可复算。

备选方案：
- 只输出各阶段求和，不做解释。结论不可审计。
- 仅输出 critical path breakdown。实现复杂，而且会丢失并行信息。

### Decision 5: 对缓存确认型写请求，区分“主机完成视角”和“后端持久化视角”

当前 `WRITE` / `STATIC_WRITE` 在数据写入控制器 cache 后即可向 Host 返回 `REQ_COMP`，与后续 flush 到 NAND 的事务解耦。本次设计不改变这一既有完成语义，但报告必须额外区分两类时间：
- `host_total_latency`: 从 `REQ_INIT` 到 Host 接收到 `REQ_COMP` 的时延。
- `persistence_total_latency`：仅在该请求数据最终被刷新到介质时存在，表示从 `REQ_INIT` 到最后一个归属后台事务完成的时延。

同时，报告为写请求新增 `persistence_status`：
- `not_applicable`：读/搜/算等同步请求。
- `persisted`：请求数据最终落盘。
- `superseded_in_cache`：请求数据在 flush 前已被后续写覆盖，没有独立落盘事务。
- `pending_without_flush`：理论保底状态；正常在本次设计中应通过最终 drain 消除。

理由：
- 如果把 `total_latency` 直接改成持久化时延，会与当前 Host 完成语义冲突，并影响已有请求流认知。
- 如果完全忽略后台持久化，则无法满足用户希望看到 TSU / PHY 阶段统计的诉求。
- 双视角输出既保留原有请求语义，又给出后台执行的解释空间。

备选方案：
- 修改写请求完成语义，等待 NAND program 后再回 `REQ_COMP`。过于激进，会破坏既有规范与测试。
- 仅统计 Host 完成视角。无法覆盖后台执行阶段。

### Decision 6: 在缓存条目和 flush 事务中维护请求 lineage，用于把后台写回归因回输入请求

`Cache_Manager` 的 user/static cache entry 需要扩展 per-sector 或 per-line 的 `origin_request_ids`。当 `write_flush()` 生成新的后台 `USER_WRITE` / `USER_STATIC_WRITE` 事务时，这些事务应携带 contributor request 集合，统计模块据此把 TSU / PHY 阶段回填到对应请求的 persistence 视角。

覆盖规则：
- 同一 sector 被后续请求覆盖时，lineage 更新为最新请求。
- 一个 flush 事务包含多个请求贡献的 sector 时，该事务会被关联到多个请求。

理由：
- 当前 flush 生成的事务 `source_req=None`，否则无法把后台延时归因到原始 trace 请求。
- 不做 per-sector lineage 时，多个请求共享同一 page flush 会丢失归因精度。

备选方案：
- 只在 page 级记录一个 origin request。会在 mixed-sector write 场景下误归因。

### Decision 7: 仿真结束前执行一次最终 cache drain，再导出报告

在 `Engine.Start_simulation(...)` 或其收尾阶段新增 finalize 步骤：当事件队列第一次清空后，主动调用 cache flush / translate / schedule，把仍留在控制器 cache 中、已准备好的写数据下发到后端；如果该操作产生新事件，则继续 `Run()` 直到队列再次清空，然后再生成请求级报告。

理由：
- 若不做最终 drain，trace 结尾处的写请求可能只有 Host 完成视角，没有任何 TSU / PHY 统计。
- 最终 drain 让报告在同一输入下稳定，避免“是否正好触发 cache pressure”影响统计完整性。
- 该行为只增加仿真尾部的已缓存数据清空，不改变中途调度策略。

备选方案：
- 不做最终 drain。实现简单，但报告对写请求不完整。
- 强制每次写都立刻 flush。会明显改变性能模型，不能接受。

### Decision 8: 报告输出路径采用 `report/<trace-stem>_request_latency.json`

报告文件名以 trace 文件名为主，例如 `report/test_read_write_request_latency.json`。文件包含 `meta`、`requests` 两个主块；如有需要，可保留 `summary` 或 `stage_definitions` 作为扩展字段。

理由：
- 与现有 `output/*.log` 分离，避免混淆日志与结构化统计。
- 以 trace 文件名命名便于批量运行、对比和归档。

备选方案：
- 固定写入单一文件名。简单但容易被覆盖。

## Design Rationale

本设计的核心取舍是“在不推翻当前请求完成语义的前提下，补齐请求级可解释统计”。因此没有选择直接改变写请求的完成路径，而是用双视角统计和 cache lineage 来把主机可见时延与后台持久化行为同时表达出来。与此同时，考虑到请求会被切分为多笔事务、事务会并行执行、PCIe 和 PHY 本身又存在多阶段拆分，单纯记录时间点不足以支撑高质量分析，所以设计改为以区间为基础、以 merged duration 为输出、以 overlap/untracked 解释偏差。这一方案虽然实现略重，但它最贴合仿真器当前的事件模型，也最容易通过自动化测试建立稳定闭环。

## Risks / Trade-offs

- [写回 lineage 增加缓存元数据复杂度] → 通过只在统计模块所需的粒度上保存 request id 集合，避免把完整请求对象嵌入 cache entry。
- [阶段区间重叠导致报告理解成本上升] → 在 JSON 中显式输出 `overlap_latency` 与 `untracked_latency`，并在 spec 中固定口径。
- [最终 cache drain 会改变仿真尾部行为] → 将其限定为“报告生成前的收尾步骤”，不改变中途队列策略，并在文档中明确该语义。
- [共享 flush 事务会被多个请求共同引用] → 采用 per-request merged interval 统计，允许共享后台阶段同时归因给多个请求，但通过 stable lineage 和测试用例验证一致性。
- [大量 hook 可能与现有调试工具相互影响] → 将 recorder 设计为显式 attach 的模块，并复用当前 timeline recorder 的 runtime patch 模式。

## Migration Plan

1. 为 `Request`、必要的 `Transaction` 和 cache entry 增加稳定标识与统计关联字段。
2. 引入请求级统计模块，实现 attach、阶段采集、区间合并和 JSON 序列化。
3. 在 `Host`、`PCIe_link`、`AMU`、`TSU`、`PHY`、`Engine` 中补充最小必要 hook 点。
4. 在引擎收尾阶段增加最终 cache drain 和报告写出。
5. 增加单元测试与端到端测试，覆盖普通读、mapping miss、缓存确认写和最终 drain 行为。
6. 若实现过程中发现统计字段不足，可增量补充 JSON schema，但保持已定义字段向后兼容。

## Open Questions

- `report/` 输出是否需要允许调用方自定义路径，还是首版仅固定目录即可。
- 是否要在首版 JSON 中同时输出详细 `intervals` 明细，还是仅输出汇总 breakdown 与少量 contributor 信息。
- `SEARCH` / `COMPUTE` 的 Host 数据请求与结果返回是否需要进一步细分为命令消息和数据消息两类 PCIe 子阶段；当前设计保留扩展能力，但首版可以先按方向聚合。
