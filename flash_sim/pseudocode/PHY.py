# -*- coding: utf-8 -*-
"""Flash 物理层：Chip/Die 状态与命令管理。"""

from typing import Dict, Tuple


class DieBKE:
    def __init__(self, die_id):
        self.die_id = die_id
        self.active_commands = []
        self.suspended_commands = []
        self.status = "idle"


class ChipBKE:
    def __init__(self, chip_id: Tuple[int, int]):
        self.chip_id = chip_id
        self.active_commands = []
        self.suspended_commands = []
        self.status = "idle"
        self.dies: Dict[int, DieBKE] = {}


class PHY:
    def __init__(self):
        self._chip_bkes: Dict[Tuple[int, int], ChipBKE] = {}

    def get_chip_bke(self, chip_id: Tuple[int, int]) -> ChipBKE:
        if chip_id not in self._chip_bkes:
            self._chip_bkes[chip_id] = ChipBKE(chip_id)
        return self._chip_bkes[chip_id]
