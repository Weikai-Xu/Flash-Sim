# Cycle-Accurate Flash 仿真器

## 目标
实现一个支持存储、搜索和计算操作的 cycle-accurate flash 仿真器，能够输出各种命令的执行延迟。

## 功能范围

### 1. 基础存储操作
- **Read**: 从指定地址读取数据
- **Write**: 向指定地址写入数据
- **Erase**: 擦除指定 block 的数据

### 2. 搜索操作 (CAM 功能)
- 同时开启多个 Word Line (WL)
- 每个 string 上的 flash cell 构成 CAM 单元进行并行搜索
- 输出: 搜索操作的延迟

### 3. 计算操作 (MAC 功能)
- 同时开启多个 Block
- 使用单个 Word Line (WL)
- 在 Bit Line (BL) 上累加 MAC 电流
- 输出: 计算操作的延迟

## 接口
- **Trace 格式**: JSON 格式
- 输入: JSON 格式的命令序列
- 输出: JSON 格式的延迟结果

## 时序模型
- 使用标准 NAND Flash 时序参数 (tR, tPROG, tBERS 等)
- 参数可配置

## 验收标准
1. 能够正确解析 JSON trace 输入
2. read/write/erase 操作返回正确的延迟
3. search 操作返回正确的延迟 (多 WL 并行搜索)
4. compute 操作返回正确的延迟 (多 Block 并行 MAC)
5. 延迟数值符合标准 NAND Flash 时序参数

## 依赖
- 无外部依赖
- 纯 Python 实现或使用 Python 可选的 C 扩展