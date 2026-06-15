## Context

当前 Flash-Sim 的 WRITE 路径中，`Address_Mapping_Unit.translate_and_submit()` 对每个 `USER_WRITE` 事务立即调用 `Block_Manager.get_write_frontier()` 分配 PPA（eager allocation）。`get_write_frontier()` 在 `free_block_pool` 为空时直接 `raise ValueError`，导致向单个 plane 密集写入时仿真崩溃（Bug A）。

Flash-Sim-NG 中已实施的方案 B（懒分配）将 PPA 分配推迟到 TSU dispatch 阶段，引入了 PPA_PENDING 状态机和延迟 invalidation 回填机制。方案 A 走相反方向：保持 eager allocation 但加背压——pool 不够时不分配、不入队，等 GC 回收 block 后再重试。

## Goals / Non-Goals

**Goals:**
- 修复 Bug A：`get_write_frontier` 在 pool 空时不崩溃
- 在 submit 阶段实现 per-plane 背压：pool ≤ 阈值时阻塞 WRITE 入队
- GC 完成时显式唤醒 waiting writes
- `write_flush` 正确处理部分成功场景

**Non-Goals:**
- 不改变 TSU 调度优先级或 per-chip 队列结构
- 不改变 GC 阈值（`GC_WL_MANAGER_FREE_BLOCK_POOL_THRESHOLD = 2`）和 victim 选择逻辑
- 不改变 Data_Cache 行为
- 不引入 PPA_PENDING / 两阶段翻译 / 延迟 invalidation

## Decisions

### D1: 背压检查位置在 `translate_and_submit`，不在 TSU

在 AMU 的 WRITE 分支中，`get_write_frontier` 调用之前插入检查：

```
translate_and_submit (WRITE):
  for each tr:
    plane = get_plane_address_for_lpa(tr.lpa)
    if free_block_pool[plane] <= STOP_SERVICING_WRITES_THRESHOLD:
        waiting_writes[plane].append(tr)
        continue                    # 不入队，不分配 PPA
    ppa = get_write_frontier(plane)
    tr.address = ppa
    update CMT/GMT
    Submit_trans(tr)
```

**理由**：背压的语义是"当前没有物理资源可分配"，应该在分配物理资源的位置做检查。放在 TSU dispatch 侧是方案 B 的思路，但那会引入 PPA_PENDING。

**备选方案**：在 `get_write_frontier` 内部检查并返回 None → 被否决，因为返回 None 后调用方（AMU）还需要知道"为什么没分配成功"才能决定是阻塞还是重试。显式检查 pool 再调 `get_write_frontier` 语义更清晰。

### D2: waiting 队列为 per-plane dict，存储在 Block_Manager

```python
# Block_Manager 新增
self.waiting_writes: dict[int, list[Transaction]] = defaultdict(list)
self.STOP_SERVICING_WRITES_THRESHOLD = 2  # 与 GC 阈值独立
```

per-plane 而非全局队列，原因是：不同 plane 的 free block 互不影响。plane 0 阻塞不应阻碍 plane 1 的写入。

**理由**：GC 回收 block 也是 per-plane 的——`finalize_gc_erase` 释放的是特定 plane 的 block，只需要唤醒对应 plane 的 waiting writes。

### D3: wakeup 在 `finalize_gc_erase` 中触发

```python
def finalize_gc_erase(self, addr):
    # ... 现有逻辑：重置 BKE、放回 free_block_pool ...
    
    # 新增：唤醒该 plane 的 waiting writes
    plane_id = addr.plane
    self._retry_waiting_writes(plane_id)
```

wakeup 时逐个重试：对 waiting 队列中的每个事务，重新走 `translate_and_submit` 的 PPA 分配路径。如果 pool 仍不够（例如只回收了 1 个 block 但有 10 个等待的写），则剩余事务继续留在 waiting 队列，等待下一次 GC 唤醒。

**理由**：GC_ERASE 是唯一能将 block 放回 free pool 的事件。在放回后立即尝试唤醒，最小化 waiting writes 的等待时间。

### D4: write_flush 部分成功处理

当前 `write_flush` 假设所有事务都能成功完成 `translate_and_submit`。引入背压后，部分事务可能被阻塞在 waiting 队列。需要处理：

```python
# HIL.write_flush
for entry in flushed_entries:
    req = build_write_request(entry)
    amu.translate_and_submit(req)
    # 检查：如果 req 的事务全部在 waiting 队列中（即未入队 TSU），
    # 则对应的 cache 条目不能 pop，需保留
    if all_pending(req):
        keep_cache_entry(entry)   # 保留，下次 flush 重试
    else:
        pop_cache_entry(entry)    # 已入队 TSU，可安全 pop
```

**理由**：cache 条目 pop 的语义是"数据已移交给下游（TSU）"。如果下游（TSU）根本没收到，pop 会导致数据丢失。

### D5: GC_WRITE 的 `allocate_gc_write_page` 同样处理

`allocate_gc_write_page` 在 `block_id < 0` 或 `write_frontier >= PAGE_PER_BLOCK` 时也抛异常。改为：GC 内部循环等待，直到有 free block 可用（或触发新一轮 GC）。

```python
def allocate_gc_write_page(self, plane_addr, block_id=None):
    if block_id is None:
        block_id = self.select_wl_aware_free_block(plane_addr)
    while block_id < 0:
        self.gc_wl_unit.check_gc()      # 再触发一次 GC
        block_id = self.select_wl_aware_free_block(plane_addr)
        # 极端情况：如果所有 block 都是 invalid-free，需要等待 ERASE 完成
        # 此处简化处理：GC_ERASE 最终会释放 block
    ...
```

**理由**：GC relocation 需要目标页，与用户写有相同约束。但 GC 路径优先级更高——没有 GC 完成就没有 free block 释放，没有 free block 释放就永远无法服务用户写。因此 GC 内部应自旋等待而非返回 None。

### D6: 背压阈值与 GC 阈值的关系

```
STOP_SERVICING_WRITES_THRESHOLD  = 2    # 背压阈值（新建）
GC_WL_MANAGER_FREE_BLOCK_POOL_THRESHOLD = 3  # GC 触发阈值（已有，见 common.py:95）
```

背压阈值 ≤ GC 阈值时，背压在 GC 有机会运行之前就介入，保留了足够的缓冲。建议初始值设为 2（与 GC 阈值 3 保持 1 个 block 的余量）。

## Design Rationale

方案 A 的核心设计理念是 **"物理资源不足时，不创建无法完成的事务"**——与方案 B 的"创建事务但不分配资源，等 dispatch 时再说"形成对比。方案 A 的优势：

1. **TSU 永远只看到 PPA 已确定的事务**：不需要 PPA_PENDING 状态、不需要 dispatch 时 `_resolve_pending_write` 分支、不需要延迟 invalidation 回填
2. **背压是显式的，不是调度器的隐式副作用**：waiting 队列的存在让"系统在等待什么"一目了然
3. **与 MQSim 对齐**：MQSim 正是在 `translate_and_submit` 阶段做 `Stop_servicing_writes` 检查

代价是新增了 waiting 队列和 GC→AMU 的回调路径，但这些是局部机制，不改变核心调度语义。

## Risks / Trade-offs

- **[R1] GC relocation 死锁**：如果 GC 本身需要 free block 来做 relocation，而所有 free block 都已耗尽 → 通过 D5 的循环等待 + check_gc 处理，必要时可以让 GC 抢占正在等待的用户写事务使用的 plane 资源
- **[R2] waiting writes 饥饿**：如果 GC 长时间不触发（例如没有足够的 invalid page 形成 victim），waiting writes 可能永久阻塞 → 当前 GC 阈值 3 保证 pool 耗尽前就会触发 GC；可以通过降低背压阈值或在 check_gc 中增加 proactive trigger 来缓解
- **[R3] write_flush 语义变更**：部分 flush 成功意味着 HIL 需要维护"哪些 cache 条目已移交给 TSU、哪些还在等待"的状态 → D4 提供最小化处理方案
- **[R4] 测试覆盖率**：现有 trace 不会触发背压（单 plane 写入 < 512 页）→ 需要 GC 压力测试 trace 覆盖背压→唤醒路径

## Open Questions

1. `STOP_SERVICING_WRITES_THRESHOLD` 的最优值？初始设为 2，是否需要可配置？
2. waiting writes 唤醒时，一次唤醒多少个？逐个还是批量？逐个重试更简单但效率较低
3. GC_WRITE 是否需要走背压路径，还是应该无条件分配（D5）？
