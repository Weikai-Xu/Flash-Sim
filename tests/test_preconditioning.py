"""
Block Manager Preconditioning 功能测试。

验证 preconditioning 函数的正确性：
1. free block pool 的大小和内容
2. write frontier block 的初始化
3. full block 中 valid/invalid page 的比例
4. plane 统计信息的准确性
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flash_sim.FTL import Block_Manager, blockBKE, PlaneBKE
from flash_sim.common import PAGE_PER_BLOCK, GC_WL_MANAGER_FREE_BLOCK_POOL_THRESHOLD, BLOCK_PER_PLANE
from flash_sim.config import FlashGeometry
import unittest


class TestPreconditioning(unittest.TestCase):
    """测试 Block Manager 的 preconditioning 功能。"""
    
    def setUp(self):
        """设置测试环境。"""
        # 使用较小的尺寸以加快测试
        self.block_manager = Block_Manager(
            channel_no=1,
            chip_no_per_channel=2,  # 1 static chip，1 regular chip
            die_no_per_chip=1,
            plane_no_per_die=1,
            block_no_per_plane=64,
            pages_per_block=PAGE_PER_BLOCK
        )
        # 注意：Block Manager 在构造时所有 block 都是 free 的
    
    def test_preconditioning_initialization(self):
        """测试 preconditioning 后 block 的初始化状态。"""
        print("\n[TEST] test_preconditioning_initialization")
        
        # 调用 preconditioning
        self.block_manager.preconditioning()
        
        # 验证 static chip 未被初始化
        # 注意：block_manager 的默认值会初始化所有 plane，所以我们只验证 regular chip
        # 获取 regular chip 的 plane
        plane_bke = self.block_manager.block_keeping_book[0][0][0][0]  # channel 0, regular chip 0
        
        # 验证 free block pool 的大小
        self.assertEqual(len(plane_bke.free_block_pool), GC_WL_MANAGER_FREE_BLOCK_POOL_THRESHOLD,
                        f"Free block pool size should be {GC_WL_MANAGER_FREE_BLOCK_POOL_THRESHOLD}")
        
        # 验证 write frontier block 已设置
        write_frontier_block_id = plane_bke.write_frontier_block
        self.assertNotIn(write_frontier_block_id, plane_bke.free_block_pool,
                        "Write frontier block should not be in free block pool")
        
        # 验证 write frontier block 的 write_frontier 值在有效范围内
        write_frontier_bke = plane_bke.block_entries[write_frontier_block_id]
        self.assertGreater(write_frontier_bke.write_frontier, 0,
                          "Write frontier should be > 0")
        self.assertLess(write_frontier_bke.write_frontier, PAGE_PER_BLOCK,
                       "Write frontier should be < PAGE_PER_BLOCK")
        
        print(f"✓ Free block pool size: {len(plane_bke.free_block_pool)}")
        print(f"✓ Write frontier block: {write_frontier_block_id} (frontier: {write_frontier_bke.write_frontier}/{PAGE_PER_BLOCK})")
    
    def test_free_block_pool_pages(self):
        """测试 free block pool 中所有 block 的 page 都是 free 的。"""
        print("\n[TEST] test_free_block_pool_pages")
        
        self.block_manager.preconditioning()
        plane_bke = self.block_manager.block_keeping_book[0][0][0][0]
        
        # 验证 free block pool 中的每个 block
        for block_id in plane_bke.free_block_pool:
            bke = plane_bke.block_entries[block_id]
            # 所有 page 应该是 free 的
            self.assertEqual(bke.free_page_count, PAGE_PER_BLOCK,
                           f"Block {block_id} in free pool should have {PAGE_PER_BLOCK} free pages")
            self.assertEqual(bke.valid_page_count, 0,
                           f"Block {block_id} in free pool should have 0 valid pages")
            self.assertEqual(bke.invalid_page_count, 0,
                           f"Block {block_id} in free pool should have 0 invalid pages")
            self.assertEqual(len(bke.valid_pages), 0)
            self.assertEqual(len(bke.invalid_pages), 0)
        
        print(f"✓ All {len(plane_bke.free_block_pool)} free blocks verified")
    
    def test_full_block_valid_invalid_ratio(self):
        """测试已写满 block 中 valid/invalid page 的比例。"""
        print("\n[TEST] test_full_block_valid_invalid_ratio")
        
        geometry = FlashGeometry()
        valid_invalid_ratio = geometry.valid_invalid_ratio
        
        self.block_manager.preconditioning()
        plane_bke = self.block_manager.block_keeping_book[0][0][0][0]
        
        # 获取所有 full block（非 free pool，非 write frontier block）
        all_blocks = set(range(self.block_manager.block_no_per_plane))
        free_blocks = plane_bke.free_block_pool
        write_frontier_block = plane_bke.write_frontier_block
        full_blocks = all_blocks - free_blocks - {write_frontier_block}
        
        print(f"Valid/Invalid ratio config: {valid_invalid_ratio}")
        print(f"Full blocks count: {len(full_blocks)}")
        
        # 验证每个 full block
        total_valid = 0
        total_invalid = 0
        for block_id in full_blocks:
            bke = plane_bke.block_entries[block_id]
            # 验证 block 是写满的
            self.assertEqual(bke.free_page_count, 0,
                           f"Full block {block_id} should have 0 free pages")
            # 验证 valid + invalid = PAGE_PER_BLOCK
            self.assertEqual(bke.valid_page_count + bke.invalid_page_count, PAGE_PER_BLOCK,
                           f"Block {block_id}: valid + invalid should equal PAGE_PER_BLOCK")
            # 验证 valid_pages 和 invalid_pages 集合正确
            self.assertEqual(len(bke.valid_pages), bke.valid_page_count)
            self.assertEqual(len(bke.invalid_pages), bke.invalid_page_count)
            # 验证没有重叠
            self.assertEqual(len(bke.valid_pages & bke.invalid_pages), 0,
                           f"Block {block_id}: valid_pages and invalid_pages should not overlap")
            
            total_valid += bke.valid_page_count
            total_invalid += bke.invalid_page_count
        
        # 验证 plane 的统计信息
        self.assertEqual(plane_bke.valid_page_count, total_valid,
                        "Plane valid_page_count should match sum of block valid_pages")
        self.assertEqual(plane_bke.invalid_page_count, total_invalid,
                        "Plane invalid_page_count should match sum of block invalid_pages")
        
        print(f"✓ Total valid pages: {total_valid}")
        print(f"✓ Total invalid pages: {total_invalid}")
        if len(full_blocks) > 0:
            actual_ratio = total_valid / (total_valid + total_invalid) if (total_valid + total_invalid) > 0 else 0
            print(f"✓ Actual valid/invalid ratio: {actual_ratio:.2f}")
    
    def test_plane_statistics(self):
        """测试 plane 统计信息的准确性。"""
        print("\n[TEST] test_plane_statistics")
        
        self.block_manager.preconditioning()
        plane_bke = self.block_manager.block_keeping_book[0][0][0][0]
        
        # 统计实际的 page 数
        total_free_pages = 0
        total_valid_pages = 0
        total_invalid_pages = 0
        
        for block_id, bke in enumerate(plane_bke.block_entries):
            total_free_pages += bke.free_page_count
            total_valid_pages += bke.valid_page_count
            total_invalid_pages += bke.invalid_page_count
        
        # 验证 plane 统计与实际值一致
        self.assertEqual(plane_bke.free_page_count, total_free_pages,
                        "Plane free_page_count mismatch")
        self.assertEqual(plane_bke.valid_page_count, total_valid_pages,
                        "Plane valid_page_count mismatch")
        self.assertEqual(plane_bke.invalid_page_count, total_invalid_pages,
                        "Plane invalid_page_count mismatch")
        
        # 验证总页数
        total_pages = total_free_pages + total_valid_pages + total_invalid_pages
        expected_total = PAGE_PER_BLOCK * self.block_manager.block_no_per_plane
        self.assertEqual(total_pages, expected_total,
                        f"Total pages should be {expected_total}")
        
        print(f"✓ Free pages: {total_free_pages}")
        print(f"✓ Valid pages: {total_valid_pages}")
        print(f"✓ Invalid pages: {total_invalid_pages}")
        print(f"✓ Total: {total_pages}/{expected_total}")
    
    def test_static_chip_skipped(self):
        """测试 static chip 在 preconditioning 中被跳过。"""
        print("\n[TEST] test_static_chip_skipped")
        
        # 创建一个 block manager 并手动检查 is_static_chip 函数
        self.block_manager.preconditioning()
        
        # 验证 static chip 判断逻辑
        # static chip 是指 chip_id >= chip_per_channel - static_chip_per_channel
        from flash_sim.common import STATIC_CHIP_PER_CHANNEL, CHIP_PER_CHANNEL
        
        for chip_id in range(self.block_manager.chip_no_per_channel):
            is_static = self.block_manager._is_static_chip(chip_id)
            expected_static = chip_id >= self.block_manager.chip_no_per_channel - STATIC_CHIP_PER_CHANNEL
            self.assertEqual(is_static, expected_static,
                           f"Static chip detection for chip {chip_id} mismatch")
        
        print(f"✓ Static chip detection correct")


if __name__ == '__main__':
    unittest.main(verbosity=2)
