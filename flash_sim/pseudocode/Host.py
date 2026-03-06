# -*- coding: utf-8 -*-
from queue import Queue

from common import (
    sim_object,
    REQ_INIT,
    WRITE,
    READ,
    SEARCH,
    COMPUTE,
    WRITE_REQ,
    READ_REQ,
    SEARCH_REQ,
    COMPUTE_REQ,
    WRITE_DATA_REQ,
    SEARCH_INPUT_REQ,
    COMPUTE_INPUT_REQ,
    WRITE_DATA_RECEIVED,
    READ_REQ_RECEIVED,
    REQ_COMP,
    SQ_INFORM,
    CQ_INFORM,
)
import PCIe_link


class Host(sim_object):
    class Memory:
        def __init__(self, queue_ptrs=None, num_of_queues=8, depth=64):
            self.storage = {}
            self.sq_entries = [[] for _ in range(num_of_queues)]
            self._queue_ptrs = queue_ptrs
            self._depth = depth

        def read(self, address: int) -> bytes:
            return self.storage.get(address, b"\x00" * 4096)

        def write(self, address: int, data: bytes):
            self.storage[address] = data

        def sq_push(self, queue_id, req):
            self.sq_entries[queue_id].append(req)
            if self._queue_ptrs is not None:
                self._queue_ptrs.sq_tails[queue_id] = (
                    self._queue_ptrs.sq_tails[queue_id] + 1
                ) % self._depth

    class Queue_ptrs:
        def __init__(self, num_of_queues, depth_of_queues):
            self.sq_heads = [0] * num_of_queues
            self.sq_tails = [0] * num_of_queues
            self.cq_heads = [0] * num_of_queues
            self.cq_tails = [0] * num_of_queues
            self.depth = depth_of_queues
            self.num_of_queues = num_of_queues

        def is_sq_empty(self, queue_id):
            return self.sq_heads[queue_id] == self.sq_tails[queue_id]

        def is_sq_full(self, queue_id):
            return (self.sq_tails[queue_id] + 1) % self.depth == self.sq_heads[queue_id]

        def find_available_sq(self):
            for i in range(self.num_of_queues):
                if not self.is_sq_full(i):
                    return i
            return None

    class IO_Flow:
        def __init__(self, sq_id=None):
            self.busy = False
            self.current_req = None
            self.sq_id = sq_id

    class IO_Flow_Manager:
        def __init__(self, flows):
            self.io_flows = flows

        def find_available_flow(self):
            for flow in self.io_flows:
                if not flow.busy:
                    return flow
            return None

    def __init__(self, name, num_of_queues, depth_of_queues):
        self.name = name
        self.num_of_queues = num_of_queues
        self.queue_ptrs = self.Queue_ptrs(num_of_queues, depth_of_queues)
        self.memory = self.Memory(
            queue_ptrs=self.queue_ptrs,
            num_of_queues=num_of_queues,
            depth=depth_of_queues,
        )
        self.pcie_link = None
        self.io_flows = [self.IO_Flow(sq_id=i) for i in range(num_of_queues)]
        self.io_flow_manager = self.IO_Flow_Manager(self.io_flows)
        self.waiting_req = Queue()

    def execute(self, event):
        assert event.type == REQ_INIT
        req = event.param
        self.submit_req(req)

    def submit_req(self, req):
        target_sq_id = self.queue_ptrs.find_available_sq()
        if target_sq_id is None:
            self.waiting_req.put(req)
            return
        self.memory.sq_push(target_sq_id, req)
        req.sq_id = target_sq_id
        flow = self.io_flow_manager.find_available_flow()
        if flow is not None:
            flow.busy = True
            flow.current_req = req
            flow.sq_id = target_sq_id
            msg_type = WRITE_REQ if req.type == WRITE else READ_REQ
            if req.type == SEARCH:
                msg_type = SEARCH_REQ
            elif req.type == COMPUTE:
                msg_type = COMPUTE_REQ
            message = PCIe_link.PCIe_message(
                type=msg_type, payload=None, source_req=req, sq_id=target_sq_id
            )
            self.pcie_link.send(message, self.pcie_link.device)

    def inform_sq_head_update(self, sq_id):
        self.pcie_link.send(
            PCIe_link.PCIe_message(
                type=SQ_INFORM,
                payload={
                    "sq_id": sq_id,
                    "new_head": self.queue_ptrs.sq_heads[sq_id],
                    "new_tail": self.queue_ptrs.sq_tails[sq_id],
                },
                source_req=None,
                sq_id=sq_id,
            ),
            self.pcie_link.device,
        )

    def inform_cq_tail_update(self, cq_id):
        self.pcie_link.send(
            PCIe_link.PCIe_message(
                type=CQ_INFORM,
                payload={
                    "cq_id": cq_id,
                    "new_head": self.queue_ptrs.cq_heads[cq_id],
                    "new_tail": self.queue_ptrs.cq_tails[cq_id],
                },
                source_req=None,
                sq_id=cq_id,
            ),
            self.pcie_link.device,
        )

    def consume_cq(self, cqe):
        cq_id = getattr(cqe, "cq_id", 0)
        self.queue_ptrs.cq_tails[cq_id] = (
            self.queue_ptrs.cq_tails[cq_id] + 1
        ) % self.queue_ptrs.depth
        self.inform_cq_tail_update(cq_id)

    def send_data(self, message):
        # 占位：根据 message 类型从 memory 取数并发送到 device
        pass

    def receive_pcie_message(self, message):
        if message.type in (WRITE_DATA_REQ, SEARCH_INPUT_REQ, COMPUTE_INPUT_REQ):
            self.send_data(message)
        elif message.type in (WRITE_DATA_RECEIVED, READ_REQ_RECEIVED):
            target_id = message.sq_id
            self.queue_ptrs.sq_heads[target_id] = (
                self.queue_ptrs.sq_heads[target_id] + 1
            ) % self.queue_ptrs.depth
            self.inform_sq_head_update(message.sq_id)
            self.io_flows[target_id].busy = False
            self.io_flows[target_id].current_req = None
            if not self.waiting_req.empty():
                next_req = self.waiting_req.get()
                self.submit_req(next_req)
        elif message.type == REQ_COMP:
            self.queue_ptrs.cq_tails[message.sq_id] = (
                self.queue_ptrs.cq_tails[message.sq_id] + 1
            ) % self.queue_ptrs.depth
            self.inform_cq_tail_update(message.sq_id)
