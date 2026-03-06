# -*- coding: utf-8 -*-
from dataclasses import dataclass

from common import Request, READ, WRITE, SEARCH, COMPUTE
from PHY import PHY
import utils

# ----- 常量 -----
CMT_SIZE = 4096
LPA_NO_PER_MAPPING_PAGE = 512
NUM_OF_QUEUES = 8
CHANNEL_NO = 8
CHIP_NO_PER_CHANNEL = 4


@dataclass
class cmt_entry:
    ppa: int
    dirty: bool


@dataclass
class Transaction:
    source_req: Request
    lpa: int
    ppa: int = 0
    mvpn: int = 0
    bitmap: int = 0


class CMT:
    def __init__(self):
        self.cache: dict[int, cmt_entry] = {}
        self.lru_list: list[int] = []

    def query(self, lpa: int) -> cmt_entry | None:
        if lpa in self.cache:
            self.lru_list.remove(lpa)
            self.lru_list.insert(0, lpa)
            return self.cache[lpa]
        return None

    def write(self, lpa: int, ppa: int, dirty: bool = True):
        entry = cmt_entry(ppa=ppa, dirty=dirty)
        if lpa in self.cache:
            self.cache[lpa] = entry
            self.lru_list.remove(lpa)
            self.lru_list.insert(0, lpa)
        else:
            if len(self.cache) >= CMT_SIZE:
                lru_lpa = self.lru_list.pop()
                del self.cache[lru_lpa]
            self.cache[lpa] = entry
            self.lru_list.insert(0, lpa)


class Block_Manager:
    def __init__(self):
        self._used_blocks: set[tuple] = set()
        self._protected_blocks: set[tuple] = set()

    def is_free(self, addr) -> bool:
        block_key = (addr[0], addr[1], addr[2], addr[3]) if len(addr) >= 4 else addr
        return block_key not in self._used_blocks

    def is_not_protected(self, addr) -> bool:
        block_key = (addr[0], addr[1], addr[2], addr[3]) if len(addr) >= 4 else addr
        return block_key not in self._protected_blocks

    def mark_used(self, addr):
        block_key = (addr[0], addr[1], addr[2], addr[3]) if len(addr) >= 4 else addr
        self._used_blocks.add(block_key)

    def mark_protected(self, addr):
        block_key = (addr[0], addr[1], addr[2], addr[3]) if len(addr) >= 4 else addr
        self._protected_blocks.add(block_key)


class GC_WL_Manager:
    def __init__(self):
        pass


def _get_lpa_sector_in_mapping_page(lpa: int) -> int:
    return lpa % LPA_NO_PER_MAPPING_PAGE


class TSU:
    def __init__(self):
        self._onfly_schedule_req_no = 0
        self.sched_priority = [
            "mapping_read",
            "user_search",
            "user_compute",
            "user_read",
            "mapping_write",
            "user_write",
            "gc_read",
            "gc_write",
        ]
        self.read_write_queues = [
            [{key: [] for key in self.sched_priority}
             for _ in range(CHIP_NO_PER_CHANNEL)]
            for _ in range(CHANNEL_NO)
        ]
        self.search_queue: list = []
        self.compute_queue: list = []
        self.block_manager = Block_Manager()
        self.channel_no = CHANNEL_NO
        self.chip_no_per_channel = CHIP_NO_PER_CHANNEL
        self.round_robin_turn = [0] * self.channel_no
        self.PHY = PHY()

    def Prepare_trans_submission(self):
        self._onfly_schedule_req_no += 1

    def Prepare_trans_issue(self):
        self.Prepare_trans_submission()

    def Submit_trans(self, payload):
        if isinstance(payload, Transaction):
            ch, chip, _, _, _ = utils.translate_ppa_to_address(payload.ppa)
            trans_type = "user_read" if payload.source_req.type == READ else "user_write"
            self.read_write_queues[ch][chip][trans_type].append(payload)
        elif isinstance(payload, Request):
            if payload.type not in (SEARCH, COMPUTE):
                raise TypeError("Only SEARCH/COMPUTE req can be issued to tsu in req form")
            if payload.type == SEARCH:
                self.search_queue.append(payload)
            else:
                self.compute_queue.append(payload)

    def Schedule(self):
        self._onfly_schedule_req_no -= 1
        if self._onfly_schedule_req_no < 0:
            raise RuntimeError("onfly_schedule_req_no should not be negative")
        if self._onfly_schedule_req_no > 0:
            return
        for i in range(self.channel_no):
            for _ in range(self.chip_no_per_channel):
                chip_id = (i, self.round_robin_turn[i])
                chip_bke = self.PHY.get_chip_bke(chip_id)
                if chip_bke.status == "idle":
                    self.activate(chip_id)
                self.round_robin_turn[i] = (self.round_robin_turn[i] + 1) % self.chip_no_per_channel
                if chip_bke.status == "active":
                    break

    def _find_another_queue_for_same_transaction_type(self, chip_id: tuple, key: str):
        ch, chip = chip_id[0], chip_id[1]
        for k in self.sched_priority:
            if k == key and len(self.read_write_queues[ch][chip][k]) > 1:
                return self.read_write_queues[ch][chip][k]
        return None

    def activate(self, chip_id):
        chip_queues = self.read_write_queues[chip_id[0]][chip_id[1]]
        for key in self.sched_priority:
            if key not in ("user_search", "user_compute"):
                queue = chip_queues[key]
                if len(queue) > 0:
                    submit_queue2 = self._find_another_queue_for_same_transaction_type(chip_id, key)
                    self.issue_read_write_command(chip_id, queue, submit_queue2 or [])
                    break
            else:
                if len(self.search_queue) > 0:
                    self.issue_search_command(chip_id, self.search_queue)
                    break
                elif len(self.compute_queue) > 0:
                    self.issue_compute_command(chip_id, self.compute_queue)
                    break

    def can_issue(self, transaction: Transaction) -> bool:
        addr = utils.translate_ppa_to_address(transaction.ppa)
        return self.block_manager.is_free(addr) and self.block_manager.is_not_protected(addr)

    def issue_read_write_command(self, chip_id, submit_queue1, submit_queue2):
        pass

    def issue_search_command(self, chip_id, search_queue):
        pass

    def issue_compute_command(self, chip_id, compute_queue):
        pass


class Address_Mapping_Domain:
    def __init__(self):
        self.cmt = CMT()
        self.gtd: dict[int, int] = {}
        self.gmt: dict[int, cmt_entry] = {}
        self.DepartingEntry = []
        self.ArrivingEntry = []
        self.tsu = TSU()

    def query(self, transaction: Transaction) -> bool:
        entry = self.cmt.query(transaction.lpa)
        if entry is not None:
            transaction.ppa = entry.ppa
            return True
        if transaction.lpa in self.gmt:
            transaction.ppa = self.gmt[transaction.lpa].ppa
            return True
        mvpn = transaction.lpa // LPA_NO_PER_MAPPING_PAGE
        if mvpn not in self.gtd:
            self.tsu.Prepare_trans_submission()
            self.tsu.Submit_trans(transaction)
            self.tsu.Schedule()
            return False
        mppn = self.gtd[mvpn]
        _ = _get_lpa_sector_in_mapping_page(transaction.lpa)
        self.tsu.Prepare_trans_submission()
        self.tsu.Submit_trans(transaction)
        self.tsu.Schedule()
        return False


class Address_Mapping_Unit:
    def __init__(self):
        self.domains = [Address_Mapping_Domain() for _ in range(NUM_OF_QUEUES)]
        self.waiting_search_compute_req: list = []
        self.waiting_read_write_trans: list = []
        self.tsu = TSU()

    def translate(self, req: Request):
        domain = self.domains[req.sq_id or 0]
        transactions = req.transaction_list
        if req.type in (READ, WRITE):
            self.tsu.Prepare_trans_submission()
            for tr in transactions:
                if domain.query(tr):
                    self.tsu.Submit_trans(tr)
                else:
                    self.waiting_read_write_trans.append(tr)
        elif req.type in (SEARCH, COMPUTE):
            all_translated = True
            for tr in transactions:
                if not domain.query(tr):
                    all_translated = False
            if all_translated:
                self.tsu.Prepare_trans_submission()
                self.tsu.Submit_trans(req)
                self.tsu.Schedule()
            else:
                self.waiting_search_compute_req.append(req)

    def handle_mapping_read_response(self, response):
        # 用 response 更新 CMT/GMT，并继续处理 waiting_read_write_trans / waiting_search_compute_req
        pass


class FTL:
    def __init__(self):
        self.address_mapping_unit = Address_Mapping_Unit()
        self.gc_wl_manager = GC_WL_Manager()
        self.block_manager = Block_Manager()

    def handle_new_req(self, req: Request):
        self.address_mapping_unit.translate(req)
