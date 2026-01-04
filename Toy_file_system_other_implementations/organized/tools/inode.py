#!/usr/bin/env python3
"""
Inode Layer - File metadata and block pointers
"""

import struct
import time

INODE_SIZE = 128
DIRECT_BLOCKS = 12


class FileType:
    """File type enumeration"""
    REGULAR = 1
    DIRECTORY = 2


class Inode:
    """Represents file metadata and block pointers"""
    
    def __init__(self, file_type):
        now = int(time.time())
        
        self.file_type = file_type
        self.size = 0
        self.block_count = 0
        self.direct_blocks = [0] * DIRECT_BLOCKS
        self.indirect_block = 0
        self.double_indirect_block = 0
        self.created = now
        self.modified = now
        self.accessed = now
    
    @classmethod
    def from_bytes(cls, data):
        """Deserialize inode from bytes"""
        file_type_val = data[0]
        if file_type_val == 1:
            file_type = FileType.REGULAR
        elif file_type_val == 2:
            file_type = FileType.DIRECTORY
        else:
            file_type = FileType.REGULAR
        
        inode = cls(file_type)
        inode.size = struct.unpack('<I', data[4:8])[0]
        inode.block_count = struct.unpack('<I', data[8:12])[0]
        
        for i in range(DIRECT_BLOCKS):
            offset = 12 + i * 4
            inode.direct_blocks[i] = struct.unpack('<I', data[offset:offset+4])[0]
        
        inode.indirect_block = struct.unpack('<I', data[60:64])[0]
        inode.double_indirect_block = struct.unpack('<I', data[64:68])[0]
        inode.created = struct.unpack('<Q', data[68:76])[0]
        inode.modified = struct.unpack('<Q', data[76:84])[0]
        inode.accessed = struct.unpack('<Q', data[84:92])[0]
        
        return inode
    
    def to_bytes(self):
        """Serialize inode to bytes"""
        data = bytearray(INODE_SIZE)
        
        data[0] = int(self.file_type)
        struct.pack_into('<I', data, 4, self.size)
        struct.pack_into('<I', data, 8, self.block_count)
        
        for i in range(DIRECT_BLOCKS):
            offset = 12 + i * 4
            struct.pack_into('<I', data, offset, self.direct_blocks[i])
        
        struct.pack_into('<I', data, 60, self.indirect_block)
        struct.pack_into('<I', data, 64, self.double_indirect_block)
        struct.pack_into('<Q', data, 68, self.created)
        struct.pack_into('<Q', data, 76, self.modified)
        struct.pack_into('<Q', data, 84, self.accessed)
        
        return bytes(data)