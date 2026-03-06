# -*- coding: utf-8 -*-
"""公共定义：sim_object、事件类型常量、Request、Event。"""

from dataclasses import dataclass, field
from typing import Any, List, Optional


# ----- 基类 -----
class sim_object:
    """仿真对象基类，Host/PCIe_link/HIL 等继承，统一 execute(event) 接口。"""
    def execute(self, event: "SimEvent") -> None:
        """事件处理入口，子类按 event.type 分发。"""
        raise NotImplementedError


# ----- 事件类型常量 -----
REQ_INIT = "REQ_INIT"
DELIVER = "DELIVER"

# PCIe message 类型（Host/Device 间）
WRITE_REQ = "WRITE_REQ"
READ_REQ = "READ_REQ"
SEARCH_REQ = "SEARCH_REQ"
COMPUTE_REQ = "COMPUTE_REQ"
WRITE_DATA = "WRITE_DATA"
SEARCH_INPUT = "SEARCH_INPUT"
COMPUTE_INPUT = "COMPUTE_INPUT"
WRITE_DATA_REQ = "WRITE_DATA_REQ"
SEARCH_INPUT_REQ = "SEARCH_INPUT_REQ"
COMPUTE_INPUT_REQ = "COMPUTE_INPUT_REQ"
WRITE_DATA_RECEIVED = "WRITE_DATA_RECEIVED"
READ_REQ_RECEIVED = "READ_REQ_RECEIVED"
REQ_COMP = "REQ_COMP"
SQ_INFORM = "SQ_INFORM"
CQ_INFORM = "CQ_INFORM"

# 请求类型（req.type，用于 FTL/HIL）
READ = "READ"
WRITE = "WRITE"
SEARCH = "SEARCH"
COMPUTE = "COMPUTE"


# ----- Request 数据类 -----
@dataclass
class Request:
    """Host 下发的 IO 请求，供 Host、HIL、FTL 使用。"""
    type: str  # READ, WRITE, SEARCH, COMPUTE
    sq_id: Optional[int] = None
    transaction_list: List[Any] = field(default_factory=list)
    serviced_trans: int = 0
    lba_start: int = 0
    lba_count: int = 0
    payload: Any = None

    def is_serviced(self) -> bool:
        """是否所有 transaction 已处理完成。"""
        if not self.transaction_list:
            return True
        return self.serviced_trans >= len(self.transaction_list)


# ----- Event 视图（供 execute(event) 使用） -----
@dataclass
class SimEvent:
    """仿真事件：type, target, param。"""
    type: str
    target: Any
    param: Any
