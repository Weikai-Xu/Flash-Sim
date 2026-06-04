## ADDED Requirements

### Requirement: Request flow preserves phase timestamps needed for latency reporting

`Host`、`PCIe_link`、`HIL`、`AMU`、`TSU` 和 `PHY` MUST 暴露请求级统计所需的阶段边界信息。至少包括：`REQ_INIT` 被执行的时间、请求进入或重入 SQ 的时间、首次经 PCIe 发送的时间、每条 PCIe 消息的发送方向/消息类型/字节数/到达时间、mapping wait 的开始与结束时间、事务进入 TSU 队列的时间、事务首次被发往 `PHY` 的时间，以及 `REQ_COMP` 回到 Host 的时间。

#### Scenario: Request waits in Host SQ before being sent

- **WHEN** 一条请求在 `Host` 中已经进入 SQ，但因为对应 `IO_Flow` 被占用而未能立即发出
- **THEN** 系统 MUST 保留足以计算该请求 `host_sq_wait` 与 `host_dispatch` 延时的阶段时间戳

#### Scenario: PCIe message carries data payload

- **WHEN** `PCIe_link` 发送一条携带 `payload["data"]` 的消息
- **THEN** 系统 MUST 保留该消息的方向、消息类型、估算字节数、发送时间和投递完成时间，以便请求级报告计算对应的 PCIe 阶段延时

### Requirement: Mapping-miss reads expose AMU waiting intervals to the reporting subsystem

当用户请求因为地址映射缺失而生成 `MAPPING_READ` 时，`AMU` MUST 为原始请求保留“等待映射返回”的区间信息；该区间从依赖 mapping 的事务被挂起开始，到映射结果返回并使事务可以重新提交或失败返回为止。

#### Scenario: Mapping read resolves a waiting user read

- **WHEN** 一条 `READ` 请求中的事务因缺少映射而等待 `MAPPING_READ` 返回，且映射随后成功返回
- **THEN** 系统 MUST 为该原始请求记录一个非零的 `amu_mapping_wait` 区间，并在事务重新进入 TSU 之前结束该区间

#### Scenario: Mapping read fails

- **WHEN** 一条等待映射的用户请求因为 `MAPPING_READ` 失败而被错误完成
- **THEN** 系统 MUST 仍然闭合该请求的 mapping-wait 区间，并使报告能够据此计算失败请求的 `amu_mapping_wait`

### Requirement: Buffered write cache preserves origin request lineage through flush

对于先写入控制器 cache 的 `WRITE` / `STATIC_WRITE` 请求，`Data_Cache` 与 `Cache_Manager` MUST 保留足够细粒度的来源请求 lineage，使 flush 生成的后台事务能够关联回原始输入请求。若多个请求共同贡献同一 flush 事务，系统 MUST 允许该后台事务同时关联到多个来源请求；若某个 cache 单元被后续写覆盖，lineage MUST 更新为最新来源。

#### Scenario: Flush transaction contains contributions from multiple requests

- **WHEN** 一个后台 flush 事务包含来自多个输入写请求的数据贡献
- **THEN** 系统 MUST 让该后台事务可被同时归因到这些来源请求，以便报告回填对应的 TSU / PHY 后台时延

#### Scenario: Later write overwrites cached data before flush

- **WHEN** 一个 cache entry 中的某个 sector 或静态写单元在 flush 之前被后续请求覆盖
- **THEN** 系统 MUST 更新该单元的 lineage 为最新请求，而不是把后台持久化时延继续归因给已被覆盖的旧请求
