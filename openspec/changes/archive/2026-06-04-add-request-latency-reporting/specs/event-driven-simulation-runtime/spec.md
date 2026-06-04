## MODIFIED Requirements

### Requirement: 仿真在事件耗尽时结束

主运行循环 SHALL 持续执行事件，直到事件队列第一次为空；如果控制器 cache 中仍存在可下发的写回数据，`Engine` MUST 在结束前触发最终 cache drain、把新增事务继续推进到事件再次耗尽。若启用了请求级延时统计，`Engine` MUST 在最终清空后导出报告，并以完成这些收尾步骤后的当前仿真时间作为最终结束时间。

#### Scenario: 事件队列清空但仍有待刷写缓存

- **WHEN** `Run()` 执行过程中事件队列已经为空，但控制器 cache 中仍有可写回的请求数据
- **THEN** `Engine` MUST 触发最终 cache drain、注册所需的后续事件，并继续执行直到新增事件也全部完成

#### Scenario: 事件队列最终清空并写出报告

- **WHEN** `Start_simulation(...)` 已执行完原始 trace 事件与最终 cache drain 产生的全部事件
- **THEN** `Engine` MUST 停止继续取事件、导出请求级统计报告，并以当前仿真时间作为最终结束时间
