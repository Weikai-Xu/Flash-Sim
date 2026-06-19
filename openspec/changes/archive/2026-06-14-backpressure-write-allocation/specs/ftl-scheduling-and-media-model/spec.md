## MODIFIED Requirements

### Requirement: Block_Manager 维护 per-plane 的 block 资源池和写前沿

`Block_Manager` SHALL 维护每个 plane / block 的 `free`、`valid`、`invalid` 页面统计、写前沿与擦写次数；SHALL 维护 per-plane waiting writes 队列用于背压阻塞的 USER_WRITE 事务；`GC_WL_Unit` MUST 在 free block pool 低于阈值时选择 GC victim block、提交 `GC_READ`、`GC_WRITE` 和 `GC_ERASE` 事务链，并在擦除完成后把该 block 按当前擦写次数放回可分配 free pool，同时显式唤醒对应 plane 的 waiting writes，并继续检查是否需要触发 static wear leveling。

#### Scenario: GC 触发与完成

- **WHEN** 某个 plane 的 `free_block_pool` 数量小于或等于 GC 阈值
- **THEN** `GC_WL_Unit` MUST 选择一个安全的 victim block，提交完整的 `GC_READ`、`GC_WRITE` 和 `GC_ERASE` 事务链，并在擦除完成后更新 block bookkeeping，且 MUST 调用 `_retry_waiting_writes(plane_id)` 唤醒被背压阻塞的写入

#### Scenario: GC 擦除完成回收 block 并唤醒等待写入

- **THEN** `Block_Manager` 和 `GC_WL_Unit` MUST 将被擦除 block 以最新 `wl_level` 重新加入可分配 free pool，在同一 plane 上继续评估是否需要 follow-up 的 static wear leveling，MUST 从该 plane 的 `waiting_writes` 队列 FIFO 取出事务重新尝试 PPA 分配和 TSU 入队

### Requirement: get_write_frontier 仅在 pool 充足时被调用

`Block_Manager.get_write_frontier()` SHALL 在 pool 充足的前提下为调用方分配下一个可用的 (block, page) PPA。调用方 MUST 在调用前自行检查 pool 余量。若 pool 为空时被调用，`get_write_frontier` SHALL 返回 None 而非抛异常，调用方 SHALL 将此视为编程错误并记录告警。

#### Scenario: 正常分配

- **WHEN** 调用方确认 pool 充足后调用 `get_write_frontier(plane_addr)`
- **THEN** 返回包含有效 (channel, chip, die, plane, block, page) 的 `FlashAddress`

#### Scenario: pool 空时被误调用

- **WHEN** `get_write_frontier` 被调用时 `free_block_pool` 为空
- **THEN** 系统 SHALL 返回 None 并打印告警日志，SHALL NOT 抛异常
