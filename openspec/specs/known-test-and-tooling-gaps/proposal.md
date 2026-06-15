## Why

在 `fix-host-sq-flow-deadlock` 修复后，test_trace 完成率达到 489/489，但批量运行全部 15 个 trace 时发现 3 个预存测试失败和 3 个工具链/报告问题。

### 预存测试失败

**1. test_search_compute — 2 条 SEARCH 请求永不完成**

所有 6 条 SEARCH 事务（4+2）和 5 条 COMPUTE 事务（2+3）全部路由到 static chip (channel=0, chip=3) 的 `plane=0`。TSU 的 `issue_search_command` 限制每个 (die, plane) 每次只能发一个事务（`plane_vector` 去重），导致 SERIAL 执行：
- SEARCH × 6 × 200µs + COMPUTE × 5 × 500µs ≈ 3.7ms
- 仿真在 0.93ms 结束 → 大量事务未完成

COMPUTE 在 static chip 调度中有优先权（`try_compute` 先于 `try_search`），因此 COMPUTE 能完成而 SEARCH 被排在后面。修复方向：放宽同一 plane 的并行限制，或延长仿真运行时间。

**2. test_read_error_cases — 1 条 READ 请求永不完成**

`req-0001-read-106688-1` (READ at time=0, lha=106688) 提交后一直没有 REQ_COMP。需要进一步定位，初步推测与 LPA 106688 的映射状态或 preconditioning 数据有关。

**3. test_multi_write — cache 容量检查失败**

`_count_new_ready_lines` 按 sector 粒度计数（每个 sector bitmap 位计为 1），但 `Data_Cache` 容量以 line 为单位（每 line = 64 sector = 1 page）。单次 WRITE size=130 产生 130 个 "new ready lines"，超过 64 line 上限触发 `ValueError`。实际只需 3 个 line（ceil(130/64) = 3 page）。

### 工具链/报告问题

**4. CSV "是否cache命中" 列语义不一致**

`_csv_cache_hit_value` 在 `data_cache_status == "full_hit"` 失败后回退到映射缓存命中判断（`mapping_resolution_counts["cmt_hit"]`）。导致 preconditioning 中有 CMT 条目但数据缓存未命中的 READ 被错误标记为"是"。例如 test_trace 中 READ at time=10 (lpa=113461)：CMT 命中（preconditioning 写入）但数据需要读 NAND（energy=0.31 μJ），CSV 却显示"是"。应统一为数据缓存命中状态。

**5. CSV 缺少 status 列**

失败请求（status=ERROR）在 CSV 中没有对应列，无法区分 SUCCESS 和 ERROR。应增加 `status` 列。

**6. main.py INPUT_JSON 硬编码**

`INPUT_JSON` 从环境变量 `FLASH_SIM_INPUT_JSON` 读取，默认硬编码 `test_case/test_trace.json`。命令行参数被忽略。运行其他 trace 必须设置环境变量。应改为 `sys.argv[1]` 或 argparse。

## Capabilities

### Modified Capabilities
- `host-device-request-flow`: SEARCH 事务调度、cache 容量检查、READ 请求错误处理
- `request-latency-reporting`: CSV "是否cache命中"列语义、status 列
- `simulator-tooling`: main.py 命令行接口

## Impact

- 测试：`test_search_compute.json`、`test_read_error_cases.json`、`test_multi_write.json`
- 工具：`flash_sim/main.py`、`flash_sim/request_latency_report.py`
- 数据：`flash_sim/HIL.py`（`_count_new_ready_lines`）

## Non-goals

- 不改变 TSU 调度优先级算法（cache pressure drain、static chip 优先级次序）
- 不改变 Data_Cache 容量策略
- 不改变 static chip 的 die-plane 并行约束

---

## 附录：GC 压力测试发现的两个 Bug

编写 GC 压力测试 trace（`test_script/generate_gc_pressure_trace.py`）时发现两个真实 simulator bug。

### Bug A：密集写触发 free block pool 耗尽

**现象**：向单个 plane 密集写入，`get_write_frontier()` 在 `free_block_pool` 空时直接 `raise ValueError` 导致仿真崩溃。

```
ValueError: [Block Manager] <get_write_frontier> plane 0 has no eligible free blocks
```

调用链：`cache_write → write_flush → translate_and_submit → get_write_frontier`

**根因**：page 分配是 eager 的（在 `translate_and_submit` 时立即分配），而 block 回收是 lazy 的（需等写完成 + GC_ERASE ≈10.25ms）。`get_write_frontier()` 不检查 free_pool 是否为空，空了直接抛异常。

| 时刻 | 事件 |
|------|------|
| ~4.8 µs | 写 → free_pool 跨过 GC 阈值 (≤3) |
| ~5.0 µs | 写 → free_pool=0 |
| ~5.1 µs | 写 → 需要 block 64 → **CRASH** |
| ~255 µs | 第一个 PHYSICAL WRITE 才完成 → `check_gc()` 首次被调用 |

**核心矛盾**：page 分配发生在纳秒级（翻译时），block 回收发生在毫秒级（GC 完成后）。当前代码在"没 block 了"时只有一条路径：抛异常。

#### 方案 A：MQSim 式背压（分配前检查）

在 `translate_and_submit` 的 `get_write_frontier` 之前加检查点，pool 不够时阻塞而非分配。

```
translate_and_submit (WRITE):
  for each tr:
    plane = get_plane_address_for_lpa(tr.lpa)
    if pool(plane) <= STOP_SERVICING_WRITES_THRESHOLD:
        waiting_writes[plane].append(tr)   # 放进 waiting 队列
        continue                           # 不分配，不提交 TSU
    page = get_write_frontier(plane)        # 分配
    update CMT → Submit_trans to TSU

GC 完成时:
  free_block_pool.add(block)
  retry_waiting_writes(plane)              # 逐个重试
```

**优点**：接近 MQSim 设计，改动集中在 AMU，Block_Manager 和 TSU 基本不动。

**缺点**：需要新增 waiting 队列 + GC 回调；背压阈值需要额外配置；`write_flush` 要处理"部分成功"（cache 条目 flush 不完）。

#### 方案 B：懒分配（dispatch 时分配）

把 `get_write_frontier` 从 `translate_and_submit`（提交时）推迟到 TSU dispatch（真正执行时）。

```
translate_and_submit (WRITE):               TSU dispatch:
  for each tr:                               chip 空闲
    plane = get_plane_address_for_lpa         get_write_frontier(plane)
    update CMT (暂不设 PPA?)                   ├─ 有 block → 分配页 → 发 PHY
    Submit_trans to TSU                        └─ 无 block → 跳过，等下次 Schedule
```

**优点**：不需要新增 waiting 队列或回调。Bug A 自然消失：dispatch 时没 block 就跳过，GC 释放 block 后下一次 `Schedule()` 自动捡起。分配时机和资源消耗时机一致。

**缺点**：CMT 更新必须跟着从 `translate_and_submit` 移到 dispatch，影响范围更大（barrier 检查、READ 的 PPA 解析等也走同一路径）。将翻译（LPA→PPA）从 submit 路径拆到 dispatch 路径是一次架构级的重构。

#### 方案对比

| 维度 | 方案 A（背压） | 方案 B（懒分配） |
|------|--------------|----------------|
| 改动范围 | AMU + GC 回调 | AMU + TSU + Block_Manager |
| 新增机制 | waiting 队列、wakeup 回调 | 无需新增 |
| 对现有架构的冲击 | 小（在现有流程上打补丁） | 大（翻译和调度分离） |
| 和 MQSim 对齐 | 是 | 不是 |
| 后续维护 | 多一套 waiting/retry 逻辑 | 简化：分配和消耗一致 |

#### 架构判断

若**只考虑当前版本快速修复**，方案 A 更合适：它保留现有 `translate_and_submit -> TSU -> PHY -> GC` 主链路，只需在写分配前增加背压和等待/唤醒机制，工程风险更低。

若**不考虑重构成本，只从长期架构演进看**，方案 B 更优。原因不是“它不需要 waiting 队列”，而是它让**物理页分配时机**与**真实资源消耗时机**重新对齐，消除了当前 eager allocation / lazy reclamation 的根本错位。对后续以下方向更友好：

- 更真实的 SSD controller 行为：调度、背压、优先级、QoS、GC/WL 协同
- 更精细的资源建模：channel/chip contention、reservation、suspend/resume
- CIM 扩展：将随机写的动态介质分配与 static region 的 `SEARCH/COMPUTE/STATIC_WRITE` 资源模型彻底分离
- 统一的“晚绑定”事务模型：请求先进入调度，再在 dispatch 时绑定最终物理资源

但方案 B 只有在把写路径改成**两阶段语义**时才成立：

1. submit 阶段只确定逻辑目标、事务类型和调度归属
2. dispatch 阶段才分配最终 PPA，并同时完成映射更新、旧页失效依赖和 barrier 建立

因此，本 proposal 的建议是：

- **短期修复 Bug A：采用方案 A**
- **长期架构演进方向：以方案 B 为目标**

### Bug B：WRITE 覆写检测只查 CMT、不查 GMT，存在遗漏 invalidation 的高风险路径

**现象**：向同一 plane 写入 420 次 + 覆写 32 次 + 持续写 40 次（TIME_STEP=2ms），仿真正常完成（518/518 SUCCESS），GC 多次触发但全部 skip——"No safe block with invalid pages found"。从运行结果看，trace 中预期的覆写并没有稳定地产生足够的 invalid page 供 GC 选择 victim。

**已确认的高风险路径**：`CMT_SIZE = 2`，极其小。`translate_and_submit(WRITE)` 只检查 CMT 来判断是否覆写（[FTL.py:1531](Flash-Sim/flash_sim/FTL.py#L1531)），不检查 GMT：

```python
if not domain.cmt.is_cached(tr.lpa):
    domain.cmt.add_entry(...)   # 视为新写
else:
    invalidation_victim_address = domain.cmt.update_entry(...)
    tr.invalidate_target = invalidation_victim_address  # 仅此处设 invalidate
```

当两次同 LPA 写入之间间隔超过 2 个不同 LPA 时，CMT 条目很容易被逐出到 GMT。此时后续覆写在代码路径上会走 `add_entry(...)` 分支，而不是 `update_entry(...)` 分支：

```
写 #1:  LPA 0 → add_entry → CMT={0, -}
写 #3:  LPA 2 → add_entry → CMT 满，逐出 LPA 0 → CMT={2, -}
写 #5:  LPA 4 → add_entry → CMT 满，逐出 LPA 2 → CMT={4, -}
...
写 #421 (覆写 LPA 0): cmt.is_cached(0) → False（旧映射可能已只存在于 GMT）
                      → add_entry (当新写) → invalidate_target = None
                      → 当前写路径不会显式拿到旧 PPA 做 _mark_invalid
```

这说明当前实现至少存在一个明确缺口：**WRITE 覆写检测依赖 CMT 命中，CMT miss 时不会回退查询 GMT**。在高 churn、小 CMT 场景下，这很可能导致旧物理页未被及时失效，进而削弱 invalid page 的形成。

**注意**：此前 proposal 中“CMT 按 domain/sq_id 隔离”的分析是错误的——当前仓库默认 `CMT_TYPE = "shared"`（[common.py:105](Flash-Sim/flash_sim/common.py#L105)），所有 domain 共享同一个 CMT 实例。因此，当前版本的核心问题不是 domain 隔离，而是 **CMT-only 覆写检测** 与极小 `CMT_SIZE` 的组合。

**修复方向**：
1. `translate_and_submit(WRITE)` 在 CMT miss 时补查 GMT，若 GMT 中已有旧映射则设置 `invalidate_target`
2. 增大 `CMT_SIZE` 以降低逐出概率，但这只能缓解症状，不能修复逻辑缺口
3. 如需更强保证，可把“覆写是否已有旧映射”的查询抽象成统一 lookup，而不是仅绑定在 CMT 命中上

### 影响范围

- `flash_sim/FTL.py`：`Block_Manager.get_write_frontier()`（Bug A）、`Address_Mapping_Unit.translate_and_submit()`（Bug A+B）
- `flash_sim/HIL.py`：无附录中已确认的直接根因；如后续复现表明 cache flush 合并策略会放大 Bug B，再单独补充
