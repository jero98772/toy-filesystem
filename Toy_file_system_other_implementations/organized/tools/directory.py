#!/usr/bin/env python3
"""
Directory Entry - Represents directory entries
"""

import struct


class DirEntry:
    """Represents a directory entry"""
    
    def __init__(self, inode_num, name):
        self.inode_num = inode_num
        self.name = name
    
    @classmethod
    def from_bytes(cls, data):
        """Deserialize directory entry, returns (entry, bytes_consumed)"""
        inode_num = struct.unpack('<I', data[0:4])[0]
        name_len = struct.unpack('<I', data[4:8])[0]
        
        name = data[8:8+name_len].decode('utf-8', errors='replace')
        total_size = 8 + name_len
        
        return cls(inode_num, name), total_size
    
    def to_bytes(self):
        """Serialize directory entry to bytes"""
        name_bytes = self.name.encode('utf-8')
        data = bytearray()
        data.extend(struct.pack('<I', self.inode_num))
        data.extend(struct.pack('<I', len(name_bytes)))
        data.extend(name_bytes)
        return bytes(data)