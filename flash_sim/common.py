# -*- coding: utf-8 -*-
"""公共定义：sim_object、事件类型常量、Request、Event。"""

from dataclasses import dataclass, field
from typing import Any, List, Optional
from enum import Enum


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
MAPPING = "MAPPING"

# 硬件配置
CHANNEL_NO = 8
CHIP_PER_CHANNEL = 4
DIE_PER_CHIP = 1
PLANE_PER_DIE = 4
BLOCK_PER_PLANE = 2048
LAYER_PER_BLOCK = 256
SL_PER_BLOCK = 2
SSL_PER_SL = 4
PAGE_PER_BLOCK = LAYER_PER_BLOCK * SL_PER_BLOCK * SSL_PER_SL
SECTOR_PER_PAGE = 64

COMPUTE_MAX_PARALLEL_SL = 256
SEARCH_MAX_PARALLEL_WL = 256
PAGE_NO_PER_SEARCH_BANK = SEARCH_MAX_PARALLEL_WL
PAGE_NO_PER_COMPUTE_BANK = COMPUTE_MAX_PARALLEL_SL * SSL_PER_SL
COMPUTE_BANK_PER_PLANE = BLOCK_PER_PLANE * SL_PER_BLOCK // COMPUTE_MAX_PARALLEL_SL
SEARCH_BANK_PER_PLANE = SSL_PER_SL * SL_PER_BLOCK * BLOCK_PER_PLANE

# ----- 常量 -----
CMT_SIZE = 4096
LPA_NO_PER_MAPPING_PAGE = 512
NUM_OF_QUEUES = 8

# ----- Die Status ----------
class DieStatus(Enum):
    READ = 1
    WRITE = 2
    SEARCH = 3
    COMPUTE = 4
    IDLE = 0

# ----- Chip Status --------
class ChipStatus(Enum):
    IDLE = 0
    READ = 1
    WRITE = 2
    SEARCH = 3
    COMPUTE = 4
    ERASE = 5
    GC_WRITE = 6



# ----- Request 数据类 -----
@dataclass
class Request:
    """Host 下发的 IO 请求，供 Host、HIL、FTL 使用。"""
    type: str  # READ, WRITE, SEARCH, COMPUTE, MAPPING
    sq_id: Optional[int] = None
    transaction_list: List[Any] = field(default_factory=list)
    serviced_trans: int = 0
    lha_start: int = 0   # start logical sector address
    size: int = 0   # size of request in sectors
    payload: Any = None

    def is_serviced(self) -> bool:
        """是否所有 transaction 已处理完成。"""
        if not self.transaction_list:
            return True
        for tr in self.transaction_list:
            if not tr.completed:
                return False
        return True

@dataclass
class FlashAddress:
    channel: int
    chip: int
    die: int
    plane: int
    sub_plane: int
    page: int

# ----- Event 视图（供 execute(event) 使用） -----
@dataclass
class SimEvent:
    """仿真事件：type, target, param。"""
    type: str
    target: Any
    param: Any


@dataclass
class cmt_entry:
    ppa: int
    dirty: bool

class GTDEntry:
    def __init__(self, address) -> None:
        self.address = address
        self.valid_bitmap = [0 for _ in LPA_NO_PER_MAPPING_PAGE]

    def set_valid_bitmap(self, lpa, value):
        self.valid_bitmap[lpa%LPA_NO_PER_MAPPING_PAGE] = value

@dataclass
class Transaction:
    source_req: Request
    type: str
    lpa: int = 0
    mvpn: int = 0
    sector_bitmap: list[int] = field(default_factory=lambda: [0] * SECTOR_PER_PAGE) # 0: not accessed, 1: accessed
    address: tuple = field(default_factory=lambda: (0, 0, 0, 0, 0, 0))
    related_transactions = []
    completed: bool = False

class Transaction_WR(Transaction):
    def __init__(self, source_req: Request, lpa: int, mvpn: int, sector_bitmap: list[int], data: bytes):
        super().__init__(source_req, lpa, mvpn, sector_bitmap)
        self.data = data

class Transaction_RD(Transaction):
    def __init__(self, source_req: Request, lpa: int, mvpn: int, sector_bitmap: list[int], address: FlashAddress):
        super().__init__(source_req, lpa, mvpn, sector_bitmap, address)
        self.type = "read"

class Transaction_SEARCH(Transaction):
    def __init__(self, source_req: Request, lpa: int, mvpn: int, sector_bitmap: list[int]):
        super().__init__(source_req, lpa, mvpn, sector_bitmap)

class DieBKE:
    def __init__(self) -> None:
        self.status = DieStatus.IDLE
        self.ActivateCommands = []
        self.SuspendedCommands = []
        

class ChipBKE:
    def __init__(self) -> None:
        self.DieKeepBook = [DieBKE() for _ in range(DIE_PER_CHIP)]
        self.status = ChipStatus.IDLE
        self.EnableWriteSuspend = False
        self.EnableEraseSuspend = False
        self.HasSuspendedCommands = False
        self.Expected_Finish_Time = 0


# ── Simulation time / event scheduling (set by Engine at startup) ──────────
_time_provider = None       # () -> int   returns current sim time in ns
_event_scheduler = None     # (event_type, target, param, scheduled_time) -> None


def CURRENT_TIME() -> int:
    """Return current simulation time in nanoseconds."""
    if _time_provider is not None:
        return _time_provider()
    return 0


def schedule_event(event_type: str, target: Any, param: Any, scheduled_time: int) -> None:
    """Register a future simulation event."""
    if _event_scheduler is not None:
        _event_scheduler(event_type, target, param, scheduled_time)


# ── Flash timing constants (nanoseconds) ────────────────────────────────────
PHY_CMD_ADDR_TIME = 100          # command + address bus transfer time
PHY_DATA_IN_TIME  = 5_000        # data transfer from controller to chip (write)
PHY_DATA_OUT_TIME = 5_000        # data transfer from chip to controller (read)
T_READ_LSB        = 75_000       # chip internal LSB read latency (tR)
T_PROG            = 1_500_000    # chip internal program latency (tPROG)
T_BERS            = 10_000_000   # chip internal erase latency (tBERS)

# ── Suspension thresholds (ns) ───────────────────────────────────────────────
REASONABLE_TIME_SUSPEND_WRITE_FOR_READ  = 100_000
REASONABLE_TIME_SUSPEND_ERASE_FOR_READ  = 1_000_000
REASONABLE_TIME_SUSPEND_ERASE_FOR_WRITE = 1_000_000

# ── PHY event type constants ─────────────────────────────────────────────────
PHY_READ_CMD_TRANSFERRED  = "PHY_READ_CMD_TRANSFERRED"   # cmd/addr sent → chip reads
PHY_WRITE_CMD_TRANSFERRED = "PHY_WRITE_CMD_TRANSFERRED"  # cmd+data sent → chip programs
PHY_ERASE_CMD_TRANSFERRED = "PHY_ERASE_CMD_TRANSFERRED"  # cmd sent → chip erases
PHY_READ_DATA_TRANSFERRED = "PHY_READ_DATA_TRANSFERRED"  # read data back to controller
PHY_CHIP_READ_COMPLETE    = "PHY_CHIP_READ_COMPLETE"     # chip internal read done
PHY_CHIP_WRITE_COMPLETE   = "PHY_CHIP_WRITE_COMPLETE"    # chip internal program done
PHY_CHIP_ERASE_COMPLETE   = "PHY_CHIP_ERASE_COMPLETE"   # chip internal erase done