#!/usr/bin/env python3
"""
Block Device Layer - Raw block I/O operations
"""

BLOCK_SIZE = 4096  # 4KB blocks


class BlockDevice:
    """Handles raw block-level I/O operations"""
    
    def __init__(self, file_path, block_count):
        self.file_path = file_path
        self.block_count = block_count
        self.file = None
    
    @classmethod
    def create(cls, path, size_mb):
        """Create a new block device with specified size"""
        total_size = size_mb * 1024 * 1024
        block_count = total_size // BLOCK_SIZE
        
        # Create and initialize file with zeros
        with open(path, 'wb') as f:
            f.write(b'\x00' * total_size)
        
        device = cls(path, block_count)
        device.file = open(path, 'r+b')
        return device
    
    @classmethod
    def open(cls, path):
        """Open an existing block device"""
        f = open(path, 'rb')
        f.seek(0, 2)  # Seek to end
        size = f.tell()
        f.close()
        block_count = size // BLOCK_SIZE
        
        device = cls(path, block_count)
        device.file = open(path, 'r+b')
        return device
    
    def read_block(self, block_num):
        """Read a single block"""
        offset = block_num * BLOCK_SIZE
        self.file.seek(offset)
        data = self.file.read(BLOCK_SIZE)
        return data
    
    def write_block(self, block_num, data):
        """Write a single block"""
        offset = block_num * BLOCK_SIZE
        self.file.seek(offset)
        self.file.write(data)
        self.file.flush()
    
    def close(self):
        """Close the block device"""
        if self.file:
            self.file.close()
            self.file = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()