## Why

`get_write_frontier()` 在 `free_block_pool` 耗尽时直接 `raise ValueError` 导致仿真崩溃（Bug A）。根因是 page 分配（eager，在 `translate_and_submit` 时立即分配）和 block 回收（lazy，GC_ERASE 需要 ~10ms）之间存在时差——纳秒级的分配速度远超毫秒级的回收速度。当前 `get_write_frontier()` 在 pool 为空时只有一条路径：抛异常。

相比已在 Flash-Sim-NG 中实施的方案 B（懒分配 / PPA_PENDING 状态机），方案 A（MQSim 式背压）改动范围更小、语义更简单：在 submit 阶段检查 pool 余量，不足时阻塞写入而非无限制分配，GC 回收 block 后显式唤醒。

## What Changes

- **BREAKING**：`Block_Manager.get_write_frontier()` 不再接受 `pool` 为空的调用——调用方必须在调用前检查 pool 余量
- 在 `Address_Mapping_Unit.translate_and_submit(WRITE)` 中新增 `free_block_pool` 背压检查：若 pool ≤ 阈值，将 WRITE 事务放入 per-plane waiting 队列，不提交 TSU
- `Block_Manager` 新增 `waiting_writes: dict[int, list[Transaction]]` per-plane waiting 队列
- `Block_Manager.finalize_gc_erase()` 在将 block 放回 free pool 后显式唤醒对应 plane 的 waiting writes，逐个重试 `translate_and_submit`
- `Block_Manager` 新增背压阈值常量 `STOP_SERVICING_WRITES_THRESHOLD`（默认值与 GC 阈值解耦，允许独立调节）
- `HIL.write_flush()` 需处理"部分成功"场景：cache flush 时若背压导致部分事务未提交 TSU，对应 cache 条目不得 pop，需保留至下次 flush 重试
- `GC_WL_Unit._submit_relocation_chain` 中 `allocate_gc_write_page` 同样需在无 free block 时处理（当前也抛异常）
- 移除 `get_write_frontier` 中的 `ValueError`，改为返回 None（调用方负责检查）

## Capabilities

### New Capabilities
- `write-backpressure`: 在 submit 阶段检查 free_block_pool 余量，不足时将 WRITE 事务阻塞在 waiting 队列而非提交 TSU；GC 回收 block 后显式唤醒

### Modified Capabilities
- `ftl-scheduling-and-media-model`: `Block_Manager.get_write_frontier` 的行为从"pool 空时抛异常"改为"pool 空时返回 None（由调用方保证不调用）"；`Block_Manager.finalize_gc_erase` 新增 wakeup waiting writes 职责；新增背压阈值常量

## Impact

- 受影响文件：`flash_sim/FTL.py`（`Block_Manager.get_write_frontier`、`Block_Manager.finalize_gc_erase`、`Address_Mapping_Unit.translate_and_submit`、`GC_WL_Unit._submit_relocation_chain`）、`flash_sim/HIL.py`（`write_flush` 部分成功处理）
- 所有现有 test_case trace 应产生一致的仿真结果（相同完成数、相同状态）
- GC 压力测试 trace（`test_script/generate_gc_pressure_trace.py`）应在不崩溃的前提下正确触发背压和唤醒

## Non-goals

- 不改变 TSU 调度优先级策略
- 不改变 GC 阈值或 victim 选择逻辑
- 不改变 Data_Cache 容量或逐出策略
- 不引入 PPA_PENDING 状态机
- 不改变 per-chip 队列结构
- 不改变 PHY、PCIe_link、Host 模块
