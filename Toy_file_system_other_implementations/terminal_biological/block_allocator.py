#!/usr/bin/env python3
"""
Block Allocator - Bitmap-based free block management
"""

class BlockAllocator:
    """Manages free block allocation using a bitmap"""
    
    def __init__(self, total_blocks):
        self.total_blocks = total_blocks
        bitmap_size = (total_blocks + 7) // 8
        self.bitmap = bytearray(bitmap_size)
        
        # Mark first few blocks as reserved for metadata
        reserved_blocks = 10
        for i in range(min(reserved_blocks, total_blocks)):
            self._set_bit(i, True)
    
    @classmethod
    def from_bytes(cls, data, total_blocks):
        """Create allocator from serialized bitmap"""
        allocator = cls.__new__(cls)
        allocator.total_blocks = total_blocks
        allocator.bitmap = bytearray(data)
        return allocator
    
    def allocate_block(self):
        """Allocate a free block, returns block number or None"""
        for i in range(self.total_blocks):
            if not self.is_allocated(i):
                self.set_allocated(i, True)
                return i
        return None
    
    def free_block(self, block_num):
        """Free a previously allocated block"""
        if block_num < self.total_blocks:
            self.set_allocated(block_num, False)
    
    def is_allocated(self, block_num):
        """Check if a block is allocated"""
        byte_idx = block_num // 8
        bit_idx = block_num % 8
        
        if byte_idx >= len(self.bitmap):
            return False
        
        return (self.bitmap[byte_idx] & (1 << bit_idx)) != 0
    
    def set_allocated(self, block_num, allocated):
        """Set allocation status of a block"""
        byte_idx = block_num // 8
        bit_idx = block_num % 8
        
        if byte_idx >= len(self.bitmap):
            return
        
        if allocated:
            self.bitmap[byte_idx] |= (1 << bit_idx)
        else:
            self.bitmap[byte_idx] &= ~(1 << bit_idx)
    
    def _set_bit(self, bit_num, value):
        """Internal helper to set a bit"""
        self.set_allocated(bit_num, value)
    
    def to_bytes(self):
        """Serialize bitmap to bytes"""
        return bytes(self.bitmap)
    
    def free_blocks(self):
        """Count free blocks"""
        free = 0
        for i in range(self.total_blocks):
            if not self.is_allocated(i):
                free += 1
        return free