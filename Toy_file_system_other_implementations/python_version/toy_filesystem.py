#!/usr/bin/env python3
"""
Toy File System Implementation in Python
A simple Unix-like filesystem with inodes, directories, and block allocation.
"""

import struct
import os
import time
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from enum import IntEnum


# Constants
BLOCK_SIZE = 4096  # 4KB blocks
MAGIC_NUMBER = 0xDEADBEEF
MAX_FILENAME_LEN = 255
INODE_SIZE = 128
DIRECT_BLOCKS = 12


# Error types
class FsError(Exception):
    """Base filesystem error"""
    pass


class InvalidFormat(FsError):
    """Invalid filesystem format"""
    pass


class FileNotFound(FsError):
    """File or directory not found"""
    pass


class DirectoryNotEmpty(FsError):
    """Directory is not empty"""
    pass


class NoSpace(FsError):
    """No space left on device"""
    pass


class InvalidPath(FsError):
    """Invalid path"""
    pass


class FileExists(FsError):
    """File already exists"""
    pass


# Layer 1: Block Layer - Raw block I/O
class BlockDevice:
    """Handles raw block-level I/O operations"""
    
    def __init__(self, file_path: Path, block_count: int):
        self.file_path = file_path
        self.block_count = block_count
        self.file = None
    
    @classmethod
    def create(cls, path: Path, size_mb: int) -> 'BlockDevice':
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
    def open(cls, path: Path) -> 'BlockDevice':
        """Open an existing block device"""
        size = os.path.getsize(path)
        block_count = size // BLOCK_SIZE
        
        device = cls(path, block_count)
        device.file = open(path, 'r+b')
        return device
    
    def read_block(self, block_num: int) -> bytes:
        """Read a single block"""
        if block_num >= self.block_count:
            raise InvalidFormat(f"Block {block_num} out of range")
        
        offset = block_num * BLOCK_SIZE
        self.file.seek(offset)
        data = self.file.read(BLOCK_SIZE)
        
        if len(data) != BLOCK_SIZE:
            raise InvalidFormat(f"Could not read full block {block_num}")
        
        return data
    
    def write_block(self, block_num: int, data: bytes):
        """Write a single block"""
        if block_num >= self.block_count:
            raise InvalidFormat(f"Block {block_num} out of range")
        
        if len(data) != BLOCK_SIZE:
            raise InvalidFormat(f"Data must be exactly {BLOCK_SIZE} bytes")
        
        offset = block_num * BLOCK_SIZE
        self.file.seek(offset)
        self.file.write(data)
        self.file.flush()
        os.fsync(self.file.fileno())
    
    def close(self):
        """Close the block device"""
        if self.file:
            self.file.close()
            self.file = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Layer 2: Block Allocation - Bitmap-based free block management
class BlockAllocator:
    """Manages free block allocation using a bitmap"""
    
    def __init__(self, total_blocks: int):
        self.total_blocks = total_blocks
        bitmap_size = (total_blocks + 7) // 8
        self.bitmap = bytearray(bitmap_size)
        
        # Mark first few blocks as reserved for metadata
        reserved_blocks = 10
        for i in range(min(reserved_blocks, total_blocks)):
            self._set_bit(i, True)
    
    @classmethod
    def from_bytes(cls, data: bytes, total_blocks: int) -> 'BlockAllocator':
        """Create allocator from serialized bitmap"""
        allocator = cls.__new__(cls)
        allocator.total_blocks = total_blocks
        allocator.bitmap = bytearray(data)
        return allocator
    
    def allocate_block(self) -> Optional[int]:
        """Allocate a free block, returns block number or None"""
        for i in range(self.total_blocks):
            if not self.is_allocated(i):
                self.set_allocated(i, True)
                return i
        return None
    
    def free_block(self, block_num: int):
        """Free a previously allocated block"""
        if block_num < self.total_blocks:
            self.set_allocated(block_num, False)
    
    def is_allocated(self, block_num: int) -> bool:
        """Check if a block is allocated"""
        byte_idx = block_num // 8
        bit_idx = block_num % 8
        
        if byte_idx >= len(self.bitmap):
            return False
        
        return (self.bitmap[byte_idx] & (1 << bit_idx)) != 0
    
    def set_allocated(self, block_num: int, allocated: bool):
        """Set allocation status of a block"""
        byte_idx = block_num // 8
        bit_idx = block_num % 8
        
        if byte_idx >= len(self.bitmap):
            return
        
        if allocated:
            self.bitmap[byte_idx] |= (1 << bit_idx)
        else:
            self.bitmap[byte_idx] &= ~(1 << bit_idx)
    
    def _set_bit(self, bit_num: int, value: bool):
        """Internal helper to set a bit"""
        self.set_allocated(bit_num, value)
    
    def to_bytes(self) -> bytes:
        """Serialize bitmap to bytes"""
        return bytes(self.bitmap)
    
    def free_blocks(self) -> int:
        """Count free blocks"""
        free = 0
        for i in range(self.total_blocks):
            if not self.is_allocated(i):
                free += 1
        return free


# Layer 3: Inode Layer - File metadata and block pointers
class FileType(IntEnum):
    """File type enumeration"""
    REGULAR = 1
    DIRECTORY = 2


class Inode:
    """Represents file metadata and block pointers"""
    
    def __init__(self, file_type: FileType):
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
    def from_bytes(cls, data: bytes) -> 'Inode':
        """Deserialize inode from bytes"""
        if len(data) < INODE_SIZE:
            raise InvalidFormat("Insufficient data for inode")
        
        file_type_val = data[0]
        if file_type_val == 1:
            file_type = FileType.REGULAR
        elif file_type_val == 2:
            file_type = FileType.DIRECTORY
        else:
            raise InvalidFormat(f"Invalid file type: {file_type_val}")
        
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
    
    def to_bytes(self) -> bytes:
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


# Directory entry structure
class DirEntry:
    """Represents a directory entry"""
    
    def __init__(self, inode_num: int, name: str):
        self.inode_num = inode_num
        self.name = name
    
    @classmethod
    def from_bytes(cls, data: bytes) -> Tuple['DirEntry', int]:
        """Deserialize directory entry, returns (entry, bytes_consumed)"""
        if len(data) < 8:
            raise InvalidFormat("Insufficient data for directory entry")
        
        inode_num = struct.unpack('<I', data[0:4])[0]
        name_len = struct.unpack('<I', data[4:8])[0]
        
        if len(data) < 8 + name_len:
            raise InvalidFormat("Insufficient data for directory entry name")
        
        name = data[8:8+name_len].decode('utf-8', errors='replace')
        total_size = 8 + name_len
        
        return cls(inode_num, name), total_size
    
    def to_bytes(self) -> bytes:
        """Serialize directory entry to bytes"""
        name_bytes = self.name.encode('utf-8')
        data = bytearray()
        data.extend(struct.pack('<I', self.inode_num))
        data.extend(struct.pack('<I', len(name_bytes)))
        data.extend(name_bytes)
        return bytes(data)


# Superblock structure
class Superblock:
    """Filesystem superblock containing metadata"""
    
    def __init__(self, total_blocks: int, inode_count: int):
        self.magic = MAGIC_NUMBER
        self.block_size = BLOCK_SIZE
        self.total_blocks = total_blocks
        self.inode_count = inode_count
        self.free_blocks = total_blocks - 10  # Reserve first 10 blocks
        self.root_inode = 1  # Root directory is inode 1
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'Superblock':
        """Deserialize superblock from bytes"""
        if len(data) < 24:
            raise InvalidFormat("Insufficient data for superblock")
        
        magic = struct.unpack('<I', data[0:4])[0]
        if magic != MAGIC_NUMBER:
            raise InvalidFormat(f"Invalid magic number: {magic:08x}")
        
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
    
    def to_bytes(self) -> bytes:
        """Serialize superblock to bytes"""
        data = bytearray(BLOCK_SIZE)
        
        struct.pack_into('<I', data, 0, self.magic)
        struct.pack_into('<I', data, 4, self.block_size)
        struct.pack_into('<I', data, 8, self.total_blocks)
        struct.pack_into('<I', data, 12, self.inode_count)
        struct.pack_into('<I', data, 16, self.free_blocks)
        struct.pack_into('<I', data, 20, self.root_inode)
        
        return bytes(data)


# Layer 4: File System - High-level file operations
class ToyFileSystem:
    """Main filesystem implementation"""
    
    def __init__(self, device: BlockDevice, allocator: BlockAllocator,
                 superblock: Superblock, inode_table: Dict[int, Inode],
                 next_inode: int):
        self.device = device
        self.allocator = allocator
        self.superblock = superblock
        self.inode_table = inode_table
        self.next_inode = next_inode
    
    @classmethod
    def create(cls, path: Path, size_mb: int) -> 'ToyFileSystem':
        """Create a new filesystem"""
        device = BlockDevice.create(path, size_mb)
        total_blocks = device.block_count
        
        # Initialize allocator
        allocator = BlockAllocator(total_blocks)
        
        # Create superblock
        inode_count = 1000  # Support up to 1000 files/directories
        superblock = Superblock(total_blocks, inode_count)
        
        # Write superblock
        device.write_block(0, superblock.to_bytes())
        
        # Write bitmap
        bitmap_data = allocator.to_bytes()
        bitmap_block = bytearray(BLOCK_SIZE)
        copy_len = min(len(bitmap_data), BLOCK_SIZE)
        bitmap_block[:copy_len] = bitmap_data[:copy_len]
        device.write_block(1, bytes(bitmap_block))
        
        # Create root directory
        inode_table = {}
        root_inode = Inode(FileType.DIRECTORY)
        inode_table[1] = root_inode
        
        # Initialize empty root directory
        root_block = allocator.allocate_block()
        if root_block is None:
            raise NoSpace("Cannot allocate root directory block")
        
        root_inode.direct_blocks[0] = root_block
        root_inode.block_count = 1
        
        # Write empty root directory block
        empty_block = bytes(BLOCK_SIZE)
        device.write_block(root_block, empty_block)
        
        # Write inode table
        cls._write_inode_table(device, inode_table)
        
        return cls(device, allocator, superblock, inode_table, next_inode=2)
    
    @classmethod
    def open(cls, path: Path) -> 'ToyFileSystem':
        """Open an existing filesystem"""
        device = BlockDevice.open(path)
        
        # Read superblock
        superblock_data = device.read_block(0)
        superblock = Superblock.from_bytes(superblock_data)
        
        # Read bitmap
        bitmap_data = device.read_block(1)
        allocator = BlockAllocator.from_bytes(bitmap_data, superblock.total_blocks)
        
        # Read inode table
        inode_table = cls._read_inode_table(device)
        
        next_inode = max(inode_table.keys(), default=1) + 1
        
        return cls(device, allocator, superblock, inode_table, next_inode)
    
    @staticmethod
    def _write_inode_table(device: BlockDevice, inode_table: Dict[int, Inode]):
        """Write inode table to disk"""
        block_data = bytearray(BLOCK_SIZE)
        offset = 0
        
        for inode_num, inode in inode_table.items():
            inode_data = inode.to_bytes()
            
            # Check if we need a new block
            if offset + 4 + INODE_SIZE > BLOCK_SIZE:
                device.write_block(2, bytes(block_data))
                block_data = bytearray(BLOCK_SIZE)
                offset = 0
            
            # Write inode number and data
            struct.pack_into('<I', block_data, offset, inode_num)
            block_data[offset+4:offset+4+INODE_SIZE] = inode_data
            offset += 4 + INODE_SIZE
        
        if offset > 0:
            device.write_block(2, bytes(block_data))
    
    @staticmethod
    def _read_inode_table(device: BlockDevice) -> Dict[int, Inode]:
        """Read inode table from disk"""
        inode_table = {}
        block_data = device.read_block(2)
        
        offset = 0
        while offset + 4 + INODE_SIZE <= BLOCK_SIZE:
            inode_num = struct.unpack('<I', block_data[offset:offset+4])[0]
            
            if inode_num == 0:
                break
            
            inode_data = block_data[offset+4:offset+4+INODE_SIZE]
            inode = Inode.from_bytes(inode_data)
            inode_table[inode_num] = inode
            
            offset += 4 + INODE_SIZE
        
        return inode_table
    
    def create_file(self, path: str):
        """Create a new file"""
        parent_path, filename = self._split_path(path)
        parent_inode_num = self._find_inode(parent_path)
        
        # Check if file already exists
        try:
            self._lookup_in_directory(parent_inode_num, filename)
            raise FileExists(f"File already exists: {path}")
        except FileNotFound:
            pass
        
        # Create new inode
        inode_num = self.next_inode
        self.next_inode += 1
        
        new_inode = Inode(FileType.REGULAR)
        self.inode_table[inode_num] = new_inode
        
        # Add to parent directory
        self._add_dir_entry(parent_inode_num, filename, inode_num)
        
        # Update on disk
        self._sync()
    
    def create_directory(self, path: str):
        """Create a new directory"""
        parent_path, dirname = self._split_path(path)
        parent_inode_num = self._find_inode(parent_path)
        
        # Check if directory already exists
        try:
            self._lookup_in_directory(parent_inode_num, dirname)
            raise FileExists(f"Directory already exists: {path}")
        except FileNotFound:
            pass
        
        # Allocate block for directory
        dir_block = self.allocator.allocate_block()
        if dir_block is None:
            raise NoSpace("Cannot allocate directory block")
        
        # Create new inode
        inode_num = self.next_inode
        self.next_inode += 1
        
        new_inode = Inode(FileType.DIRECTORY)
        new_inode.direct_blocks[0] = dir_block
        new_inode.block_count = 1
        
        self.inode_table[inode_num] = new_inode
        
        # Initialize empty directory block
        empty_block = bytes(BLOCK_SIZE)
        self.device.write_block(dir_block, empty_block)
        
        # Add to parent directory
        self._add_dir_entry(parent_inode_num, dirname, inode_num)
        
        # Update on disk
        self._sync()
    
    def write_file(self, path: str, data: bytes):
        """Write data to a file"""
        inode_num = self._find_inode(path)
        inode = self.inode_table.get(inode_num)
        
        if inode is None:
            raise FileNotFound(f"File not found: {path}")
        
        if inode.file_type != FileType.REGULAR:
            raise InvalidPath(f"Not a regular file: {path}")
        
        # Free existing blocks
        for i in range(inode.block_count):
            if i < DIRECT_BLOCKS and inode.direct_blocks[i] != 0:
                self.allocator.free_block(inode.direct_blocks[i])
                inode.direct_blocks[i] = 0
        
        # Calculate blocks needed
        blocks_needed = (len(data) + BLOCK_SIZE - 1) // BLOCK_SIZE
        
        # Allocate and write blocks
        written = 0
        for i in range(min(blocks_needed, DIRECT_BLOCKS)):
            block = self.allocator.allocate_block()
            if block is None:
                raise NoSpace("Cannot allocate data block")
            
            inode.direct_blocks[i] = block
            
            block_data = bytearray(BLOCK_SIZE)
            to_write = min(len(data) - written, BLOCK_SIZE)
            block_data[:to_write] = data[written:written+to_write]
            
            self.device.write_block(block, bytes(block_data))
            written += to_write
        
        inode.size = len(data)
        inode.block_count = blocks_needed
        inode.modified = int(time.time())
        
        self._sync()
    
    def read_file(self, path: str) -> bytes:
        """Read data from a file"""
        inode_num = self._find_inode(path)
        inode = self.inode_table.get(inode_num)
        
        if inode is None:
            raise FileNotFound(f"File not found: {path}")
        
        if inode.file_type != FileType.REGULAR:
            raise InvalidPath(f"Not a regular file: {path}")
        
        data = bytearray()
        remaining = inode.size
        
        for i in range(inode.block_count):
            if i >= DIRECT_BLOCKS:
                break  # TODO: Implement indirect blocks
            
            block_num = inode.direct_blocks[i]
            if block_num == 0:
                break
            
            block_data = self.device.read_block(block_num)
            to_read = min(remaining, BLOCK_SIZE)
            data.extend(block_data[:to_read])
            remaining -= to_read
            
            if remaining == 0:
                break
        
        return bytes(data)
    
    def list_directory(self, path: str) -> List[str]:
        """List contents of a directory"""
        inode_num = self._find_inode(path)
        inode = self.inode_table.get(inode_num)
        
        if inode is None:
            raise FileNotFound(f"Directory not found: {path}")
        
        if inode.file_type != FileType.DIRECTORY:
            raise InvalidPath(f"Not a directory: {path}")
        
        entries = []
        
        # Read directory blocks
        for i in range(inode.block_count):
            if i >= DIRECT_BLOCKS:
                break
            
            block_num = inode.direct_blocks[i]
            if block_num == 0:
                break
            
            block_data = self.device.read_block(block_num)
            offset = 0
            
            while offset < BLOCK_SIZE:
                if block_data[offset] == 0:
                    break
                
                try:
                    entry, size = DirEntry.from_bytes(block_data[offset:])
                    entries.append(entry.name)
                    offset += size
                except InvalidFormat:
                    break
        
        return entries
    
    def delete_file(self, path: str):
        """Delete a file"""
        parent_path, filename = self._split_path(path)
        parent_inode_num = self._find_inode(parent_path)
        file_inode_num = self._lookup_in_directory(parent_inode_num, filename)
        
        inode = self.inode_table.get(file_inode_num)
        if inode is None:
            raise FileNotFound(f"File not found: {path}")
        
        # Free blocks
        for i in range(inode.block_count):
            if i < DIRECT_BLOCKS and inode.direct_blocks[i] != 0:
                self.allocator.free_block(inode.direct_blocks[i])
        
        # Remove from inode table
        del self.inode_table[file_inode_num]
        
        # Remove from parent directory
        self._remove_dir_entry(parent_inode_num, filename)
        
        self._sync()
    
    def get_file_info(self, path: str) -> 'FileInfo':
        """Get file information"""
        inode_num = self._find_inode(path)
        inode = self.inode_table.get(inode_num)
        
        if inode is None:
            raise FileNotFound(f"File not found: {path}")
        
        return FileInfo(
            file_type=inode.file_type,
            size=inode.size,
            created=inode.created,
            modified=inode.modified,
            accessed=inode.accessed
        )
    
    def get_stats(self) -> 'FsStats':
        """Get filesystem statistics"""
        return FsStats(
            total_blocks=self.superblock.total_blocks,
            free_blocks=self.allocator.free_blocks(),
            total_inodes=self.superblock.inode_count,
            used_inodes=len(self.inode_table)
        )
    
    def _find_inode(self, path: str) -> int:
        """Find inode number for a given path"""
        if path == "/":
            return self.superblock.root_inode
        
        parts = [p for p in path.strip('/').split('/') if p]
        current_inode = self.superblock.root_inode
        
        for part in parts:
            current_inode = self._lookup_in_directory(current_inode, part)
        
        return current_inode
    
    def _lookup_in_directory(self, dir_inode_num: int, name: str) -> int:
        """Look up a name in a directory, returns inode number"""
        inode = self.inode_table.get(dir_inode_num)
        
        if inode is None:
            raise FileNotFound(f"Directory inode {dir_inode_num} not found")
        
        if inode.file_type != FileType.DIRECTORY:
            raise InvalidPath(f"Inode {dir_inode_num} is not a directory")
        
        for i in range(inode.block_count):
            if i >= DIRECT_BLOCKS:
                break
            
            block_num = inode.direct_blocks[i]
            if block_num == 0:
                continue
            
            block_data = self.device.read_block(block_num)
            offset = 0
            
            while offset < BLOCK_SIZE:
                if block_data[offset] == 0:
                    break
                
                try:
                    entry, size = DirEntry.from_bytes(block_data[offset:])
                    if entry.name == name:
                        return entry.inode_num
                    offset += size
                except InvalidFormat:
                    break
        
        raise FileNotFound(f"Entry '{name}' not found in directory")
    
    def _add_dir_entry(self, dir_inode_num: int, name: str, inode_num: int):
        """Add an entry to a directory"""
        entry = DirEntry(inode_num, name)
        entry_bytes = entry.to_bytes()
        
        inode = self.inode_table.get(dir_inode_num)
        if inode is None:
            raise FileNotFound(f"Directory inode {dir_inode_num} not found")
        
        # For simplicity, just use the first block
        if inode.block_count == 0:
            # Allocate first block for directory
            new_block = self.allocator.allocate_block()
            if new_block is None:
                raise NoSpace("Cannot allocate directory block")
            inode.direct_blocks[0] = new_block
            inode.block_count = 1
            block_num = new_block
        else:
            block_num = inode.direct_blocks[0]
        
        block_data = bytearray(self.device.read_block(block_num))
        
        # Find space for new entry
        offset = 0
        while offset < BLOCK_SIZE:
            if block_data[offset] == 0:
                break
            
            try:
                _, size = DirEntry.from_bytes(bytes(block_data[offset:]))
                offset += size
            except InvalidFormat:
                break
        
        if offset + len(entry_bytes) > BLOCK_SIZE:
            raise NoSpace("Directory block is full")
        
        # Write entry
        block_data[offset:offset+len(entry_bytes)] = entry_bytes
        self.device.write_block(block_num, bytes(block_data))
    
    def _remove_dir_entry(self, dir_inode_num: int, name: str):
        """Remove an entry from a directory"""
        inode = self.inode_table.get(dir_inode_num)
        
        if inode is None:
            raise FileNotFound(f"Directory inode {dir_inode_num} not found")
        
        for i in range(inode.block_count):
            if i >= DIRECT_BLOCKS:
                break
            
            block_num = inode.direct_blocks[i]
            if block_num == 0:
                continue
            
            block_data = bytearray(self.device.read_block(block_num))
            entries = []
            offset = 0
            
            # Parse all entries
            while offset < BLOCK_SIZE:
                if block_data[offset] == 0:
                    break
                
                try:
                    entry, size = DirEntry.from_bytes(bytes(block_data[offset:]))
                    if entry.name != name:
                        entries.append(entry)
                    offset += size
                except InvalidFormat:
                    break
            
            # Rewrite block without the deleted entry
            block_data = bytearray(BLOCK_SIZE)
            write_offset = 0
            
            for entry in entries:
                entry_bytes = entry.to_bytes()
                if write_offset + len(entry_bytes) <= BLOCK_SIZE:
                    block_data[write_offset:write_offset+len(entry_bytes)] = entry_bytes
                    write_offset += len(entry_bytes)
            
            self.device.write_block(block_num, bytes(block_data))
            return
        
        raise FileNotFound(f"Entry '{name}' not found")
    
    def _split_path(self, path: str) -> Tuple[str, str]:
        """Split path into parent and filename"""
        path = path.rstrip('/')
        
        if path == "/":
            raise InvalidPath("Cannot split root path")
        
        pos = path.rfind('/')
        if pos == -1:
            return "/", path
        elif pos == 0:
            return "/", path[1:]
        else:
            return path[:pos], path[pos+1:]
    
    def _sync(self):
        """Sync filesystem state to disk"""
        # Update superblock
        self.superblock.free_blocks = self.allocator.free_blocks()
        self.device.write_block(0, self.superblock.to_bytes())
        
        # Update bitmap
        bitmap_data = self.allocator.to_bytes()
        bitmap_block = bytearray(BLOCK_SIZE)
        copy_len = min(len(bitmap_data), BLOCK_SIZE)
        bitmap_block[:copy_len] = bitmap_data[:copy_len]
        self.device.write_block(1, bytes(bitmap_block))
        
        # Update inode table
        self._write_inode_table(self.device, self.inode_table)
    
    def close(self):
        """Close the filesystem"""
        self.device.close()


class FileInfo:
    """File information structure"""
    
    def __init__(self, file_type: FileType, size: int, created: int,
                 modified: int, accessed: int):
        self.file_type = file_type
        self.size = size
        self.created = created
        self.modified = modified
        self.accessed = accessed
    
    def __repr__(self):
        return (f"FileInfo(type={self.file_type.name}, size={self.size}, "
                f"created={self.created}, modified={self.modified})")


class FsStats:
    """Filesystem statistics"""
    
    def __init__(self, total_blocks: int, free_blocks: int,
                 total_inodes: int, used_inodes: int):
        self.total_blocks = total_blocks
        self.free_blocks = free_blocks
        self.total_inodes = total_inodes
        self.used_inodes = used_inodes
    
    def __repr__(self):
        return (f"FsStats(blocks: {self.total_blocks - self.free_blocks}/"
                f"{self.total_blocks}, inodes: {self.used_inodes}/"
                f"{self.total_inodes})")


def main():
    """CLI interface for interacting with the filesystem"""
    import sys
    
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <command> [args...]")
        print("Commands:")
        print("  create <img_file> <size_mb> - Create new filesystem")
        print("  mount <img_file> - Mount existing filesystem (interactive)")
        return
    
    command = sys.argv[1]
    
    if command == "create":
        if len(sys.argv) != 4:
            print(f"Usage: {sys.argv[0]} create <img_file> <size_mb>")
            return
        
        img_path = Path(sys.argv[2])
        try:
            size_mb = int(sys.argv[3])
        except ValueError:
            print(f"Invalid size: {sys.argv[3]}")
            return
        
        try:
            fs = ToyFileSystem.create(img_path, size_mb)
            fs.close()
            print(f"Created filesystem: {img_path}")
        except Exception as e:
            print(f"Error creating filesystem: {e}")
    
    elif command == "mount":
        if len(sys.argv) != 3:
            print(f"Usage: {sys.argv[0]} mount <img_file>")
            return
        
        img_path = Path(sys.argv[2])
        
        try:
            fs = ToyFileSystem.open(img_path)
        except Exception as e:
            print(f"Error opening filesystem: {e}")
            return
        
        print(f"Mounted filesystem: {img_path}")
        print("Interactive shell - type 'help' for commands, 'quit' to exit")
        
        while True:
            try:
                cmd_input = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            
            if not cmd_input:
                continue
            
            parts = cmd_input.split(maxsplit=2)
            cmd = parts[0]
            
            try:
                if cmd == "help":
                    print("Commands:")
                    print("  ls <path>        - List directory")
                    print("  mkdir <path>     - Create directory")
                    print("  touch <path>     - Create empty file")
                    print("  write <path> <text> - Write text to file")
                    print("  read <path>      - Read file content")
                    print("  rm <path>        - Delete file")
                    print("  info <path>      - Show file info")
                    print("  stats            - Show filesystem statistics")
                    print("  quit             - Exit")
                
                elif cmd == "ls":
                    path = parts[1] if len(parts) > 1 else "/"
                    entries = fs.list_directory(path)
                    for entry in entries:
                        print(f"  {entry}")
                
                elif cmd == "mkdir":
                    if len(parts) < 2:
                        print("Usage: mkdir <path>")
                        continue
                    fs.create_directory(parts[1])
                    print(f"Created directory: {parts[1]}")
                
                elif cmd == "touch":
                    if len(parts) < 2:
                        print("Usage: touch <path>")
                        continue
                    fs.create_file(parts[1])
                    print(f"Created file: {parts[1]}")
                
                elif cmd == "write":
                    if len(parts) < 3:
                        print("Usage: write <path> <text>")
                        continue
                    fs.write_file(parts[1], parts[2].encode('utf-8'))
                    print(f"Wrote to file: {parts[1]}")
                
                elif cmd == "read":
                    if len(parts) < 2:
                        print("Usage: read <path>")
                        continue
                    data = fs.read_file(parts[1])
                    try:
                        text = data.decode('utf-8')
                        print(text)
                    except UnicodeDecodeError:
                        print(f"Binary data (length: {len(data)} bytes)")
                
                elif cmd == "rm":
                    if len(parts) < 2:
                        print("Usage: rm <path>")
                        continue
                    fs.delete_file(parts[1])
                    print(f"Deleted: {parts[1]}")
                
                elif cmd == "info":
                    if len(parts) < 2:
                        print("Usage: info <path>")
                        continue
                    info = fs.get_file_info(parts[1])
                    print(f"Type: {info.file_type.name}")
                    print(f"Size: {info.size} bytes")
                    print(f"Created: {info.created}")
                    print(f"Modified: {info.modified}")
                    print(f"Accessed: {info.accessed}")
                
                elif cmd == "stats":
                    stats = fs.get_stats()
                    print(f"Total blocks: {stats.total_blocks}")
                    print(f"Free blocks: {stats.free_blocks}")
                    print(f"Used blocks: {stats.total_blocks - stats.free_blocks}")
                    print(f"Total inodes: {stats.total_inodes}")
                    print(f"Used inodes: {stats.used_inodes}")
                    print(f"Free inodes: {stats.total_inodes - stats.used_inodes}")
                
                elif cmd == "quit":
                    break
                
                else:
                    print(f"Unknown command: {cmd}. Type 'help' for available commands.")
            
            except Exception as e:
                print(f"Error: {e}")
        
        fs.close()
    
    else:
        print(f"Unknown command: {command}")
        print("Use 'create' or 'mount'")


if __name__ == "__main__":
    main()