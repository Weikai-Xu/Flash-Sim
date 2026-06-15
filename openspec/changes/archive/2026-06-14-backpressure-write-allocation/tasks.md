## 1. Block_Manager 基础设施

- [x] 1.1 在 `Block_Manager.__init__` 中新增 `waiting_writes: dict[int, list[Transaction]]` (per-plane) 和 `STOP_SERVICING_WRITES_THRESHOLD = 2` 常量
- [x] 1.2 新增 `Block_Manager.get_free_pool_count(plane_addr) -> int` 方法，返回指定 plane 的 `free_block_pool` 大小
- [x] 1.3 新增 `Block_Manager.enqueue_waiting_write(plane_id, tr)` 方法，将事务追加到 waiting 队列
- [x] 1.4 新增 `Block_Manager._retry_waiting_writes(plane_id)` 方法：FIFO 遍历 waiting 队列，对每个事务调用 AMU 的 PPA 分配路径；pool 不足时停止并保留剩余事务在队列中

## 2. get_write_frontier 语义修改

- [x] 2.1 将 `Block_Manager.get_write_frontier` 中的 `raise ValueError("no eligible free blocks")` 改为 `print` 告警日志 + `return None`
- [x] 2.2 同样修改 `Block_Manager.allocate_gc_write_page` 中 `block_id < 0` 的 ValueError → 改为循环等待 + check_gc，最终返回有效 PPA

## 3. AMU translate_and_submit 背压检查

- [x] 3.1 在 `Address_Mapping_Unit.translate_and_submit(WRITE)` 的事务循环中，`get_write_frontier` 调用之前，插入背压检查：若 `free_block_pool[plane] <= STOP_SERVICING_WRITES_THRESHOLD`，调用 `enqueue_waiting_write` 并将该事务 `continue`（跳过 PPA 分配和 TSU 入队）
- [x] 3.2 确保被阻塞的事务不更新 CMT/GMT（没有 PPA 可写），不设 `invalidate_target`，不提交 TSU

## 4. GC 唤醒 waiting writes

- [x] 4.1 在 `Block_Manager.finalize_gc_erase` 末尾（`free_block_pool.add` 之后）调用 `_retry_waiting_writes(plane_id)`
- [x] 4.2 确保 `_retry_waiting_writes` 中成功分配的事务正确完成 CMT/GMT 更新、invalidate_target 设置和 TSU 入队

## 5. write_flush 部分成功处理

- [x] 5.1 在 `HIL.write_flush` 中，调用 `translate_and_submit` 后检查每个 flush 的请求是否全部事务成功入队 TSU
- [x] 5.2 若某请求有事务因背压阻塞在 waiting 队列，对应 cache 条目保留不 pop，等待下次 flush 重试
- [x] 5.3 新增辅助方法或标记位，使 HIL 能区分"已入队"和"被背压阻塞"的事务

## 6. 测试与验证

- [x] 6.1 运行现有 15 个 test_case trace，确认无回归（相同完成数、相同状态）
- [x] 6.2 使用 GC 压力测试 trace (`test_script/generate_gc_pressure_trace.py --time-step 0`) 验证背压正确触发且仿真不崩溃
- [x] 6.3 在日志中验证背压→GC 触发→唤醒→继续写入的完整链路
