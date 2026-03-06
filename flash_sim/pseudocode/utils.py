# -*- coding: utf-8 -*-
"""FTL 用工具：PPA 与地址解析。"""

# 与 FTL 常量一致，用于将 ppa 解析为 (channel, chip, die, block, page) 等
CHANNEL_NO = 8
CHIP_NO_PER_CHANNEL = 4
DIES_PER_CHIP = 1
BLOCKS_PER_DIE = 1024
PAGES_PER_BLOCK = 128


def translate_ppa_to_address(ppa: int) -> tuple:
    """将 PPA 整数解析为 (channel, chip, die, block, page) 元组，供 Block_Manager 使用。"""
    if ppa < 0:
        return (0, 0, 0, 0, 0)
    page = ppa % PAGES_PER_BLOCK
    ppa //= PAGES_PER_BLOCK
    block = ppa % BLOCKS_PER_DIE
    ppa //= BLOCKS_PER_DIE
    die = ppa % DIES_PER_CHIP
    ppa //= DIES_PER_CHIP
    chip = ppa % CHIP_NO_PER_CHANNEL
    channel = ppa // CHIP_NO_PER_CHANNEL
    return (channel, chip, die, block, page)
