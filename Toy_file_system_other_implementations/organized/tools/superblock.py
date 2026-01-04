#!/usr/bin/env python3
"""
Superblock - Filesystem metadata
"""

import struct

BLOCK_SIZE = 4096
MAGIC_NUMBER = 0xDEADBEEF


class Superblock:
    """Filesystem superblock containing metadata"""
    
    def __init__(self, total_blocks, inode_count):
        self.magic = MAGIC_NUMBER
        self.block_size = BLOCK_SIZE
        self.total_blocks = total_blocks
        self.inode_count = inode_count
        self.free_blocks = total_blocks - 10  # Reserve first 10 blocks
        self.root_inode = 1  # Root directory is inode 1
    
    @classmethod
    def from_bytes(cls, data):
        """Deserialize superblock from bytes"""
        magic = struct.unpack('<I', data[0:4])[0]
        
        block_size = struct.unpack('<I', data[4:8])[0]
        total_blocks = struct.unpack('<I', data[8:12])[0]
        inode_count = struct.unpack('<I', data[12:16])[0]
        free_blocks = struct.unpack('<I', data[16:20])[0]
        root_inode = struct.unpack('<I', data[20:24])[0]
        
        sb = cls(total_blocks, inode_count)
        sb.block_size = block_size
        sb.free_blocks = free_blocks
        sb.root_inode = root_inode
        
        return sb
    
    def to_bytes(self):
        """Serialize superblock to bytes"""
        data = bytearray(BLOCK_SIZE)
        
        struct.pack_into('<I', data, 0, self.magic)
        struct.pack_into('<I', data, 4, self.block_size)
        struct.pack_into('<I', data, 8, self.total_blocks)
        struct.pack_into('<I', data, 12, self.inode_count)
        struct.pack_into('<I', data, 16, self.free_blocks)
        struct.pack_into('<I', data, 20, self.root_inode)
        
        return bytes(data)