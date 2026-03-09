# 本文件为仿真流程概览伪代码，仅作流程参考。
# 实际可运行入口请使用 simulator.Engine 与 simulator.Run()。

import sys

REQ_INIT = "REQ_INIT"
DELIVER = "DELIVER"
WRITE_REQ = "WRITE_REQ"


def construct_objects():
    pass


def gen_io_flow():
    pass


class Engine:
    def __init__(self) -> None:
        self.event_queue = []
        construct_objects()
        gen_io_flow()

    def start_simulation(self):
        while self.event_queue:
            event = self.event_queue.pop(0)
            if event.type == REQ_INIT:
                assert event.target == self.host
                self.host.memory.sq_push(event.param.sq_id, event.param)
            elif event.type == DELIVER:
                assert event.target == self.pcie_link
                message = event.param
                self.pcie_link.host_to_device_queue.put(message)
            elif event.type == "DELIVER_TO_DEVICE":
                assert event.target == self.device.hil
                message = event.param
                if message.type == WRITE_REQ:
                    pass


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        trace_file = sys.argv[1]
        output_file = sys.argv[2]
    engine = Engine()
    engine.start_simulation()
