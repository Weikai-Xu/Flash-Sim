# -*- coding: utf-8 -*-
from queue import Queue
from typing import Mapping

from common import *
from FTL import FTL, Transaction
from Cache import Cache
import PCIe_link
import utils
from math import ceil


class HIL(sim_object):
    def __init__(self, name, host, device):
        self.name = name
        self.host = host
        self.device = device
        # 使用 host.pcie_link 以便 Engine 注入后生效
        self._host = host
        num_queues = getattr(host, "num_of_queues", 8)
        self.input_streams = [Queue() for _ in range(num_queues)]
        self.cache_manager = Cache_Manager()
        self.ftl = FTL()
        self._sq_head_tail = {}
        self._cq_head_tail = {}

    def execute(self, event):
        self.receive_pcie_message(event.param)

    def segment(self, req):
        """根据 req 的 lha_start 和 size 范围拆成 transaction_list。"""
        # only segment once
        if req.transaction_list:
            return
        # only segment read and write requests
        if req.type in (SEARCH, COMPUTE):
            start_sub_plane_id = lha_start - xxx
            """... to be completed """

        if req.type in (READ, WRITE, MAPPING):
            start_lha = req.lha_start
            lha_count = req.size

            start_lpa = start_lha // SECTOR_PER_PAGE
            head_margin_sectors  = start_lha % SECTOR_PER_PAGE
            tail_margin_sectors = (SECTOR_PER_PAGE - (lha_count + head_margin_sectors)%SECTOR_PER_PAGE) % SECTOR_PER_PAGE

            lpa_count = max(1, ceil((lha_count + head_margin_sectors) / SECTOR_PER_PAGE))
            if lpa_count == 1: # only access one page
                bitmap = [0] * head_margin_sectors + [1] * lha_count + [0] * tail_margin_sectors
                tr = Transaction(source_req=req, lpa=start_lpa, sector_bitmap=bitmap)
                req.transaction_list.append(tr)
                return
            # access multiple pages
            for i in range(lpa_count):
                lpa = start_lpa + i
                if i == 0:
                    sector_bitmap = [1] * head_margin_sectors + [0] * (SECTOR_PER_PAGE - head_margin_sectors)
                elif i == lpa_count - 1:
                    sector_bitmap = [1] * (lha_count + head_margin_sectors - tail_margin_sectors) + [0] * tail_margin_sectors
                else:
                    sector_bitmap = [1] * SECTOR_PER_PAGE
                tr = Transaction(source_req=req, lpa=lpa, sector_bitmap=sector_bitmap)
                req.transaction_list.append(tr)

        raise ValueError("Unexpected req type!")

        
       

    def fetch_data(self, req):
        """向 host 请求 WRITE/SEARCH/COMPUTE 所需数据（占位）。"""
        pass

    def sq_update(self, sq_id, new_head, new_tail):
        self._sq_head_tail[sq_id] = (new_head, new_tail)

    def cq_update(self, cq_id, new_head, new_tail):
        self._cq_head_tail[cq_id] = (new_head, new_tail)

    def receive_pcie_message(self, message):
        target_queue = self.input_streams[message.sq_id]
        req = message.source_req
        target_queue.put(req)
        if message.type in (READ_REQ, WRITE_DATA, SEARCH_INPUT, COMPUTE_INPUT):
            self.segment(req) # 将req拆分成transaction_list
            self.cache_manager.service(req) # 查询cache，如果命中则直接返回
            if req.is_serviced():
                comp_msg = PCIe_link.PCIe_message(
                    type=REQ_COMP, payload=None, source_req=req, sq_id=req.sq_id
                )
                self._host.pcie_link.send(comp_msg, self.host)
                return
            self.ftl.handle_new_req(req)
        elif message.type in (WRITE_REQ, SEARCH_REQ, COMPUTE_REQ):
            self.fetch_data(req)
            self.segment(req)
            self.ftl.handle_new_req(req)
        elif message.type == SQ_INFORM:
            param = message.payload
            self.sq_update(param["sq_id"], param["new_head"], param["new_tail"])
        elif message.type == CQ_INFORM:
            param = message.payload
            self.cq_update(param["cq_id"], param["new_head"], param["new_tail"])


class Cache_Manager:
    def __init__(self):
        self.cache = Cache()
        self._lru_list: list[int] = []

    def service(self, req):
        if req.type == READ:
            self.query_cache(req)
            return
        if req.type in (WRITE, SEARCH, COMPUTE):
            self.write_cache(req)
            return
        raise TypeError("Unsupported req type for cache manager")

    def query_cache(self, req):
        for tr in req.transaction_list:
            data = self.cache.get(tr.lpa)
            if data is not None:
                setattr(tr, "cached_data", data)
                req.serviced_trans += 1
        # cache miss 的 transaction 留在 list 中，由 FTL 处理

    def write_cache(self, req):
        for tr in req.transaction_list:
            data = getattr(tr, "data", b"\x00" * 4096)
            self.cache.put(tr.lpa, data)
