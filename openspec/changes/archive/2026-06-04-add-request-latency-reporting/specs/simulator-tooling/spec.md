## ADDED Requirements

### Requirement: Event-driven tooling exports request latency reports under the report directory

事件驱动仿真入口在完成仿真后 SHALL 把请求级延时统计导出到 `report/` 目录，而不是混入纯文本运行日志。输出文件名 MUST 能够从输入 trace 文件稳定派生，以避免不同 trace 的报告互相覆盖。

#### Scenario: Engine entrypoint writes a trace-scoped report file

- **WHEN** 用户通过 `flash_sim/main.py` 或其他事件驱动入口运行一个名为 `<trace>.json` 的 trace
- **THEN** 系统 MUST 在 `report/` 目录下生成一个与 `<trace>` 对应的请求级 JSON 报告文件

#### Scenario: Different traces do not overwrite each other's reports

- **WHEN** 用户依次运行两个不同文件名的事件驱动 trace
- **THEN** 系统 MUST 为它们生成两个不同的请求级报告文件，而不是复用单一固定文件名

### Requirement: Request latency reports remain machine-readable and testable

请求级报告 MUST 采用稳定的 JSON 结构，至少包含 `meta` 与 `requests` 顶层字段；每条请求记录 MUST 使用固定字段名表达总时延、阶段 breakdown 和状态信息，以便自动化测试直接加载和断言，而不依赖控制台日志文本。

#### Scenario: Automated test validates a generated report

- **WHEN** 一个自动化测试在仿真结束后读取请求级报告文件
- **THEN** 测试 MUST 能够仅通过解析 JSON 结构断言请求数量、阶段字段存在性以及关键延时值，而不需要解析 stdout 或 `output/*.log`
