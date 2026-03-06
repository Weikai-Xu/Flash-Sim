# 当前架构：
FTL直接查字典完成lha-ppa映射，没考虑DFTL方法下的CMT调度
Host和HIL都没有，trace文件中的每条req直接顺序调用FTL映射下去执行
Flash Chip层面给出了每个操作的延时（没细看有没有计算数据规模的影响）

# 更改内容
## Simulator Engine
simulator.py中混合了engine和object的功能，为了架构更清晰还是将其独立开，单独写一个engine用来推进仿真，其余模块中均只有函数方法和成员参数，只能被调用，没有主动发起的进程

## Host
host执行event queue中的事件将req压入sq为仿真起点，一条trace的结果返回cq为仿真终点（host处理cq的速度一般比返回的快，所以后续不再考虑）
