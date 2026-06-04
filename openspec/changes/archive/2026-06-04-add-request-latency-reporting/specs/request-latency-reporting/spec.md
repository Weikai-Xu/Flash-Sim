## ADDED Requirements

### Requirement: Event-driven simulation exports one latency report entry per input request

当事件驱动仿真完成后，系统 SHALL 在 `report/` 目录下导出一个请求级 JSON 报告。报告 MUST 为输入 trace 中的每一条请求生成一条记录，并包含稳定的请求标识、trace 顺序、请求类型、输入地址范围、请求状态和总时延字段。

#### Scenario: Successful simulation writes a per-request report

- **WHEN** `Engine.Start_simulation(trace_path)` 成功完成一条包含多个请求的事件驱动 trace
- **THEN** 系统 MUST 在 `report/` 目录下生成与该 trace 对应的 JSON 文件，且 `requests` 数组长度 MUST 与输入 trace 请求数一致

### Requirement: Each request report includes breakdown latency for Host, PCIe, AMU, TSU, and PHY stages

每条请求记录 MUST 输出按阶段划分的 breakdown 字段，至少包括 `host_sq_wait`、`host_dispatch`、`pcie_host_to_device`、`pcie_device_to_host`、`amu_mapping_wait`、`tsu_queue_wait`、`phy_cmd_addr`、`phy_data_in`、`phy_array_exec` 和 `phy_data_out`。对于未经过某阶段的请求，该阶段值 MUST 为 `0`。系统 MUST 同时输出用于解释并行与空档的 `overlap_latency` 和 `untracked_latency` 字段。

#### Scenario: Read request with mapping miss reports AMU and PHY stages

- **WHEN** 一条 `READ` 请求因为目标映射未命中而触发 `MAPPING_READ`，随后再执行用户页读取
- **THEN** 该请求的报告记录 MUST 具有非零的 `amu_mapping_wait`、`tsu_queue_wait`、`phy_cmd_addr`、`phy_array_exec` 和 `phy_data_out` 字段

#### Scenario: Request bypasses a stage

- **WHEN** 一条请求在其生命周期中没有经过某个统计阶段
- **THEN** 报告 MUST 保留该 breakdown 字段，并将其值写为 `0` 而不是省略该字段

### Requirement: Breakdown totals must remain explainable under parallel execution

系统 MUST 按阶段合并同类区间后计算 breakdown 时长，并保证 `sum(base_stage_latencies) - overlap_latency + untracked_latency = total_latency`。其中 `base_stage_latencies` 指所有基础 breakdown 阶段字段的合计，不含 reconciliation 字段。

#### Scenario: Parallel request transactions create overlap

- **WHEN** 同一请求的多个事务在不同 chip / die 上并行推进，导致不同阶段区间在时间轴上发生重叠
- **THEN** 报告 MUST 通过非零 `overlap_latency` 或 `untracked_latency` 字段解释该请求的总时延与 breakdown 之间的差异

### Requirement: Buffered writes distinguish host-visible completion from media persistence

对于 `WRITE` 或 `STATIC_WRITE` 这类先在控制器 cache 中完成的请求，报告 MUST 同时区分主机可见完成和后端持久化状态。每条此类请求记录 MUST 包含 `host_total_latency` 与 `persistence_status`；当请求数据最终写入介质时，报告 MUST 额外包含 `persistence_total_latency` 以及对应的 TSU / PHY breakdown 贡献；当请求数据在 flush 前已被覆盖时，报告 MUST 将 `persistence_status` 标记为 `superseded_in_cache`。

#### Scenario: Cached write later reaches NAND

- **WHEN** 一条 `WRITE` 请求先在控制器 cache 中完成，随后其数据在后续 flush 或最终 drain 中被写入 flash 阵列
- **THEN** 该请求的报告 MUST 同时包含 `host_total_latency`、`persistence_total_latency` 和 `persistence_status="persisted"`

#### Scenario: Cached write is superseded before flush

- **WHEN** 一条写请求对应的数据在控制器 cache 中被后续写覆盖，且该请求不再拥有独立的后台持久化事务
- **THEN** 该请求的报告 MUST 保留 `host_total_latency`，并将 `persistence_status` 标记为 `superseded_in_cache`
