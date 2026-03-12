# -*- coding: utf-8 -*-
from queue import PriorityQueue

if __package__ in (None, ""):
    import os
    import sys

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from flash_sim import Host
    from flash_sim import pcie_link
    from flash_sim import Device
    from flash_sim import common as _common
    from flash_sim.common import EventType, SimEvent, Request, RequestType
    from flash_sim.parser import parse_trace
else:
    from . import Host
    from . import pcie_link
    from . import Device
    from . import common as _common
    from .common import EventType, SimEvent, Request, RequestType
    from .parser import parse_trace

class Engine:
    def __init__(self):
        print("Initializing simulation engine...")
        self.current_time = 0
        self.event_queue = PriorityQueue()

        # Provide simulation time and event scheduling to all modules via common.py
        _common._time_provider = lambda: self.current_time
        _common._event_scheduler = self.Register_event

        self.host = Host.Host("Host", num_of_queues=8, depth_of_queues=64)
        self.device = Device.Device(self.host)
        self.pcie_link = pcie_link.PCIe_link(self.host, self.device)
        self.host.pcie_link = self.pcie_link
        self.pcie_link.engine = self
        print("Engine initialization complete.")

    def Register_event(self, event_type, target, param, scheduled_time):
        event = SimEvent(type=event_type, target=target, time=scheduled_time, param=param)
        self.event_queue.put(event)

    def Execute_event(self):
        event = self.event_queue.get()
        if event.ignored:
            return
        self.current_time = event.time
        event.target.execute(event)

    def Run(self):
        while not self.event_queue.empty():
            self.Execute_event()
    
    def Get_current_time(self):
        return self.current_time
    
    def Initialize_event_queue(self, trace_path: str):
        """从 trace 文件解析请求，通过 Register_event 将每个 req 作为 event.param 压入 event_queue。"""
        commands = parse_trace(trace_path)
        for cmd in commands:
            scheduled_time = cmd["time"]
            req = Request(
                type=RequestType(cmd["type"].upper()),
                sq_id=None,
                transaction_list=[],
                serviced_trans=0,
                lha_start=cmd["start_lha"],
                size=cmd["size"],
            )
            self.Register_event(EventType.REQ_INIT, self.host, req, scheduled_time)

    def Start_simulation(self):
        self.Initialize_event_queue("../examples/test_trace.json")
        print("Initialization complete.")
        print(f"event_queue 初始化后内容: {list(self.event_queue.queue)}")
        self.Run()

