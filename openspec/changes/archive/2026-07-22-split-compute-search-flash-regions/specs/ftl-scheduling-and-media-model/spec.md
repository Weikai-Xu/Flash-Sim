## MODIFIED Requirements

### Requirement: 静态区域请求必须映射到专用 static chip 路径

`COMPUTE`、`SEARCH` 和 `STATIC_WRITE` SHALL 使用 region-aware static/CIM 地址映射计算物理地址。`COMPUTE` 事务 MUST 映射到 compute chip 范围并仅由 compute chip 调度；`SEARCH` 事务 MUST 映射到 search chip 范围并仅由 search chip 调度；`STATIC_WRITE` 事务 MUST 映射到 static-write chip 范围并仅由 static-write chip 调度。所有范围 MUST 在每个 channel 内以完整 chip 为粒度划分。

#### Scenario: Compute 请求进入 compute chip 路径

- **WHEN** `HIL` 为 `COMPUTE` 切分事务
- **THEN** 每个事务 MUST 带有 compute 区域物理地址，并在后续调度中只进入 compute chip 的事务队列

#### Scenario: Search 请求进入 search chip 路径

- **WHEN** `HIL` 为 `SEARCH` 切分事务
- **THEN** 每个事务 MUST 带有 search 区域物理地址，并在后续调度中只进入 search chip 的事务队列

#### Scenario: Static write 请求进入 static-write chip 路径

- **WHEN** `HIL` 为 `STATIC_WRITE` 切分事务
- **THEN** 每个事务 MUST 带有 static-write 区域物理地址，并在后续调度中只进入 static-write chip 的事务队列

## MODIFIED Requirements

### Requirement: TSU 以每 chip 队列为中心执行优先级调度

`TSU` SHALL 维护按 `channel -> chip -> transaction_type` 分组的事务队列，并在 channel 空闲时以 round-robin 方式遍历 chip，按事务优先级和 chip 类型尝试激活请求。对于普通数据 chip，默认优先级仍以当前读、写、擦除顺序为基础；但当 `Data_Cache` 因容量耗尽而触发 flush，且仍存在由该 flush 生成并等待落盘的 `USER_WRITE` 事务时，TSU MUST 进入 cache-pressure drain mode，在这些普通 chip 上优先尝试 `USER_WRITE`，直到这批累积写事务全部写入 flash array 后再恢复常规优先级。compute chip、search chip 和 static-write chip MUST 按各自请求类型独立调度，不得执行其他 CIM/static 请求类型。

#### Scenario: Channel 空闲触发常规调度

- **WHEN** 某个 channel 变为空闲、至少一个 chip 上存在待执行事务，且当前不存在待清空的 cache-pressure flush 写入 backlog
- **THEN** `TSU` MUST 按轮询顺序检查该 channel 下的 chip，并根据读、写、擦除或 region-specific static/CIM chip 的请求类型尝试下发事务

#### Scenario: cache 满触发的 flush backlog 优先写入 flash

- **WHEN** `Data_Cache` 的一次满容量 flush 已经把累积条目提交给 `AMU`，且这些 flush 生成的 `USER_WRITE` 事务仍未全部完成
- **THEN** `TSU` MUST 在普通数据 chip 上先尝试调度这些 `USER_WRITE` 事务，再考虑新的 `USER_READ`，并持续该优先级直到这批 flush backlog 全部写入 flash array

#### Scenario: Compute chip 不调度 search 请求

- **WHEN** compute chip 队列中存在 `USER_SEARCH` 或 `USER_STATIC_WRITE` 事务
- **THEN** `TSU` MUST NOT dispatch those transactions from that compute chip

#### Scenario: Search chip 不调度 compute 请求

- **WHEN** search chip 队列中存在 `USER_COMPUTE` 或 `USER_STATIC_WRITE` 事务
- **THEN** `TSU` MUST NOT dispatch those transactions from that search chip
