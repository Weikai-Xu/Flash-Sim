## ADDED Requirements

### Requirement: WRITE submit 阶段背压检查

在 `Address_Mapping_Unit.translate_and_submit(WRITE)` 中，对每个 `USER_WRITE` 事务，在调用 `get_write_frontier` 分配 PPA 之前，系统 SHALL 检查目标 plane 的 `free_block_pool` 是否大于 `STOP_SERVICING_WRITES_THRESHOLD`。若 pool 数量 ≤ 阈值，该事务 MUST NOT 分配 PPA、MUST NOT 提交到 TSU，而是放入 Block_Manager 的 per-plane waiting 队列。

#### Scenario: pool 充足时正常分配

- **WHEN** `translate_and_submit` 处理一个 `USER_WRITE` 事务，且目标 plane 的 `free_block_pool` 数量 > `STOP_SERVICING_WRITES_THRESHOLD`
- **THEN** 系统 MUST 调用 `get_write_frontier` 分配 PPA，更新 CMT/GMT 映射，并将事务提交到 TSU

#### Scenario: pool 不足时阻塞写入

- **WHEN** `translate_and_submit` 处理一个 `USER_WRITE` 事务，且目标 plane 的 `free_block_pool` 数量 ≤ `STOP_SERVICING_WRITES_THRESHOLD`
- **THEN** 该事务 MUST 被追加到 `Block_Manager.waiting_writes[plane_id]` 队列中，MUST NOT 调用 `get_write_frontier`，MUST NOT 提交到 TSU

#### Scenario: 密集写不崩溃

- **WHEN** 向单个 plane 连续提交超过其物理容量的 WRITE 请求
- **THEN** 仿真 MUST NOT 崩溃；前 N 次写入正常分配 PPA 并入队 TSU，后续写入 MUST 进入 waiting 队列等待 GC 释放 block

### Requirement: GC 完成后唤醒 waiting writes

当 `Block_Manager.finalize_gc_erase()` 将一个 block 放回 `free_block_pool` 后，系统 SHALL 尝试唤醒对应 plane 的 waiting writes。唤醒时 SHALL 对 waiting 队列中的每个事务重新执行 PPA 分配逻辑：若 pool 仍然不足，剩余事务 MUST 继续留在 waiting 队列等待下一次 GC 唤醒。

#### Scenario: GC 释放 block 后唤醒

- **WHEN** `finalize_gc_erase` 将一个 block 放回某 plane 的 `free_block_pool`，且该 plane 的 waiting 队列非空
- **THEN** 系统 MUST 从该 plane 的 waiting 队列中取出事务，按 FIFO 顺序重新尝试 PPA 分配和 TSU 入队

#### Scenario: 唤醒后 pool 仍不足

- **WHEN** waiting 队列中有多个事务等待，GC 只释放了 1 个 block，pool 数量在服务若干事务后再次降至 ≤ 阈值
- **THEN** 已成功分配 PPA 的事务 MUST 正常入队 TSU；剩余未处理的事务 MUST 留在 waiting 队列中

### Requirement: write_flush 处理部分成功

`HIL.write_flush()` 在将 cache 条目 flush 为 WRITE 请求并调用 `translate_and_submit` 后，SHALL 检查每个请求的事务是否全部成功提交到 TSU。若某个请求的任意事务因背压被阻塞在 waiting 队列，对应的 cache 条目 MUST NOT 被 pop，必须保留以等待后续 flush 重试。仅当事务已成功入队 TSU（即已分配 PPA 并调用 `Submit_trans`），对应的 cache 条目才能安全释放。

#### Scenario: 全部事务成功入队

- **WHEN** `write_flush` 提交的请求中所有事务都成功分配 PPA 并入队 TSU
- **THEN** 对应 cache 条目 MUST 被 pop

#### Scenario: 部分事务因背压阻塞

- **WHEN** `write_flush` 提交的请求中至少有一个事务因 `free_block_pool` 不足被放入 waiting 队列
- **THEN** 对应 cache 条目 MUST NOT 被 pop，SHALL 保留在 Data_Cache 中以供后续 flush 重试

### Requirement: 背压阈值独立于 GC 阈值

背压阈值 `STOP_SERVICING_WRITES_THRESHOLD` SHALL 是一个与 `GC_WL_MANAGER_FREE_BLOCK_POOL_THRESHOLD` 独立的配置常量。默认值 SHALL 为 2，确保在 GC 阈值 3 触发之前背压先行介入。

#### Scenario: 背压在 GC 之前介入

- **WHEN** free_block_pool 从充足逐渐减少到 2，此时 GC 尚未触发（GC 阈值为 3）
- **THEN** 背压 MUST 在 pool = 2 时阻塞新 WRITE 入队，为 GC 保留操作余量
