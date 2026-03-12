# -*- coding: utf-8 -*-
from queue import Queue
from typing import TYPE_CHECKING, Any

from .common import EventType
from dataclasses import dataclass
from .common import MessageType, Request

if TYPE_CHECKING:
    from .engine import Engine

@dataclass
class PCIe_message:
    type: MessageType
    payload: dict[str, Any]

class PCIe_link:
    def __init__(self, host, device):
        self.host = host
        self.device = device
        self.engine: Engine  # 在 Engine 中注入后生效
        self.host_to_device_queue = Queue()
        self.device_to_host_queue = Queue()

    def send(self, message, target):
        if target == self.device:
            self.host_to_device_queue.put(message)
            estimated_latency = self.estimate_latency(message)
            estimated_finish_time = self.engine.current_time + estimated_latency
            self.Register_sim_event(EventType.DELIVER, self.device, message, estimated_finish_time)
        elif target == self.host:
            self.device_to_host_queue.put(message)
            estimated_latency = self.estimate_latency(message)
            estimated_finish_time = self.engine.current_time + estimated_latency
            self.Register_sim_event(EventType.DELIVER, self.host, message, estimated_finish_time)

    def estimate_latency(self, message):
        return 100

    def Register_sim_event(self, event_type, target, param, scheduled_time):
        self.engine.Register_event(event_type, target, param, scheduled_time)

    def execute(self, event):
        assert event.type == EventType.DELIVER
        message = event.param
        target = event.target
        if target == self.device:
            new_message = self.host_to_device_queue.get() if not self.host_to_device_queue.empty() else None
            if new_message is not None:
                self.send(new_message, self.device)
        elif target == self.host:
            new_message = self.device_to_host_queue.get() if not self.device_to_host_queue.empty() else None
            if new_message is not None:
                self.send(new_message, self.host)
        target.receive_pcie_message(message)
