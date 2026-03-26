# -*- coding: utf-8 -*-
"""FTL 用工具：PPA 与地址解析。"""

from .common import *

def translate_ppa_to_address(ppa: int) -> FlashAddress:
    page_id = ppa % PAGE_PER_BLOCK
    ppa //= PAGE_PER_BLOCK
    sub_plane_id = ppa % BLOCK_PER_PLANE
    ppa //= BLOCK_PER_PLANE
    plane_id = ppa % PLANE_PER_DIE
    ppa //= PLANE_PER_DIE
    die_id = ppa % DIE_PER_CHIP
    ppa //= DIE_PER_CHIP
    chip_id = ppa % CHIP_PER_CHANNEL
    channel_id = ppa // CHIP_PER_CHANNEL
    return FlashAddress(channel=channel_id, chip=chip_id, die=die_id, plane=plane_id, sub_plane=sub_plane_id, page=page_id)


def translate_address_to_ppa(address: FlashAddress) -> int:
    channel_id = address.channel
    chip_id = address.chip
    die_id = address.die
    plane_id = address.plane
    sub_plane_id = address.sub_plane
    page_id = address.page
    return (((((channel_id * CHIP_PER_CHANNEL + chip_id) * DIE_PER_CHIP + die_id) * PLANE_PER_DIE + plane_id) * BLOCK_PER_PLANE + sub_plane_id) * PAGE_PER_BLOCK + page_id)

def translate_lpa_to_search_address(lpa: int) -> tuple:
    """将 LPA 整数解析为 (channel, chip, die, plane, search_bank) 元组，供 Search_Manager 使用。"""
    if lpa < 0:
        return (0, 0, 0, 0, 0)
    search_bank = lpa % SEARCH_BANK_PER_PLANE
    lpa //= SEARCH_BANK_PER_PLANE
    plane = lpa % PLANE_PER_DIE
    lpa //= PLANE_PER_DIE
    die = lpa % DIE_PER_CHIP
    lpa //= DIE_PER_CHIP
    chip = lpa % CHIP_PER_CHANNEL
    channel = lpa // CHIP_PER_CHANNEL
    return (channel, chip, die, plane, search_bank)

def translate_lha_to_lpa(lha: int) -> int:
    if lha < STATIC_BASE_LHA:
        return lha // SECTOR_PER_PAGE
    else:
        return lha - STATIC_BASE_LHA + STATIC_BASE_LHA // SECTOR_PER_PAGE

def translate_lpa_to_search_bank_id(lpa: int) -> int:
    """返回 LPA 对应的 search_bank 编号，与 translate_lpa_to_search_address 最后一维一致。"""
    return translate_lpa_to_search_address(lpa)[-1]


def translate_lpa_to_compute_address(lpa: int) -> tuple:
    """将 LPA 整数解析为 (channel, chip, die, plane, compute_bank) 元组，供 Compute 使用。"""
    if lpa < 0:
        return (0, 0, 0, 0, 0)
    compute_bank = lpa % COMPUTE_BANK_PER_PLANE
    lpa //= COMPUTE_BANK_PER_PLANE
    plane = lpa % PLANE_PER_DIE
    lpa //= PLANE_PER_DIE
    die = lpa % DIE_PER_CHIP
    lpa //= DIE_PER_CHIP
    chip = lpa % CHIP_PER_CHANNEL
    channel = lpa // CHIP_PER_CHANNEL
    return (channel, chip, die, plane, compute_bank)


def translate_lpa_to_compute_bank_id(lpa: int) -> int:
    """返回 LPA 对应的 compute_bank 编号，与 translate_lpa_to_compute_address 最后一维一致。"""
    return translate_lpa_to_compute_address(lpa)[-1]
