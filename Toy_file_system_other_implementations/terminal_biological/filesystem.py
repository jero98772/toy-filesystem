#!/usr/bin/env python3
"""
DNA Filesystem - Complete filesystem implementation using DNA storage
"""

import struct
import time
from block_device import DNABlockDevice, BLOCK_SIZE
from dna_codec import DNACodec

# Import original components (we'll reuse most of them)
import sys
sys.path.append('/mnt/user-data/uploads')

from inode import Inode, FileType, INODE_SIZE
from directory import DirEntry
from superblock import Superblock
from block_allocator import BlockAllocator


class DNAFileSystem:
    """Complete filesystem implementation using DNA-based block storage"""
    
    # Block layout:
    # Block 0: Superblock
    # Block 1: Inode bitmap
    # Block 2-3: Block allocation bitmap
    # Block 4+: Inode table
    # Remaining: Data blocks
    
    def __init__(self, device, superblock, allocator, inodes):
        self.device = device
        self.superblock = superblock
        self.allocator = allocator
        self.inodes = inodes  # Dictionary: inode_num -> Inode
        self.inode_bitmap = [False] * superblock.inode_count
    
    @classmethod
    def create(cls, path, size_mb, ecc_symbols=10):
        """Create a new DNA filesystem"""
        # Create DNA block device
        device = DNABlockDevice.create(path, size_mb, ecc_symbols)
        
        total_blocks = device.block_count
        inode_count = min(1024, total_blocks // 4)  # 1 inode per 4 blocks, max 1024
        
        # Create superblock
        superblock = Superblock(total_blocks, inode_count)
        
        # Create block allocator
        allocator = BlockAllocator(total_blocks)
        
        # Reserve blocks for metadata
        inode_blocks_needed = (inode_count * INODE_SIZE + BLOCK_SIZE - 1) // BLOCK_SIZE
        metadata_blocks = 4 + inode_blocks_needed
        
        for i in range(metadata_blocks):
            allocator.set_allocated(i, True)
        
        # Create empty inode table
        inodes = {}
        
        # Create root directory (inode 1)
        root_inode = Inode(FileType.DIRECTORY)
        inodes[1] = root_inode
        
        # Create filesystem object
        fs = cls(device, superblock, allocator, inodes)
        fs.inode_bitmap[1] = True
        
        # Write initial metadata
        fs._write_superblock()
        fs._write_allocator()
        fs._write_inodes()
        
        return fs
    
    @classmethod
    def open(cls, path, ecc_symbols=10):
        """Open an existing DNA filesystem"""
        device = DNABlockDevice.open(path, ecc_symbols)
        
        # Read superblock
        sb_data = device.read_block(0)
        superblock = Superblock.from_bytes(sb_data)
        
        # Read allocator
        alloc_data = device.read_block(2) + device.read_block(3)
        allocator = BlockAllocator.from_bytes(alloc_data, superblock.total_blocks)
        
        # Read inodes
        inodes = {}
        inode_bitmap = [False] * superblock.inode_count
        
        inode_blocks_needed = (superblock.inode_count * INODE_SIZE + BLOCK_SIZE - 1) // BLOCK_SIZE
        inode_data = b''
        
        for i in range(inode_blocks_needed):
            inode_data += device.read_block(4 + i)
        
        # Parse inodes
        for i in range(superblock.inode_count):
            offset = i * INODE_SIZE
            inode_bytes = inode_data[offset:offset+INODE_SIZE]
            
            # Check if inode is used (non-zero data)
            if any(b != 0 for b in inode_bytes[:4]):
                inode = Inode.from_bytes(inode_bytes)
                inodes[i] = inode
                inode_bitmap[i] = True
        
        fs = cls(device, superblock, allocator, inodes)
        fs.inode_bitmap = inode_bitmap
        
        return fs
    
    def _write_superblock(self):
        """Write superblock to block 0"""
        sb_data = self.superblock.to_bytes()
        self.device.write_block(0, sb_data)
    
    def _write_allocator(self):
        """Write block allocator to blocks 2-3"""
        alloc_data = self.allocator.to_bytes()
        self.device.write_block(2, alloc_data[:BLOCK_SIZE])
        if len(alloc_data) > BLOCK_SIZE:
            self.device.write_block(3, alloc_data[BLOCK_SIZE:BLOCK_SIZE*2])
    
    def _write_inodes(self):
        """Write inode table to disk"""
        inode_blocks_needed = (self.superblock.inode_count * INODE_SIZE + BLOCK_SIZE - 1) // BLOCK_SIZE
        inode_data = bytearray(inode_blocks_needed * BLOCK_SIZE)
        
        for inode_num, inode in self.inodes.items():
            offset = inode_num * INODE_SIZE
            inode_bytes = inode.to_bytes()
            inode_data[offset:offset+INODE_SIZE] = inode_bytes
        
        for i in range(inode_blocks_needed):
            block_data = bytes(inode_data[i*BLOCK_SIZE:(i+1)*BLOCK_SIZE])
            self.device.write_block(4 + i, block_data)
    
    def _allocate_inode(self):
        """Allocate a new inode number"""
        for i in range(1, self.superblock.inode_count):
            if not self.inode_bitmap[i]:
                self.inode_bitmap[i] = True
                return i
        return None
    
    def _free_inode(self, inode_num):
        """Free an inode"""
        if inode_num in self.inodes:
            del self.inodes[inode_num]
        self.inode_bitmap[inode_num] = False
    
    def _read_inode_data(self, inode):
        """Read all data blocks referenced by an inode"""
        data = bytearray()
        
        # Read direct blocks
        for block_num in inode.direct_blocks:
            if block_num == 0:
                break
            block_data = self.device.read_block(block_num)
            data.extend(block_data)
        
        return bytes(data[:inode.size])
    
    def _write_inode_data(self, inode, data):
        """Write data to inode's blocks"""
        inode.size = len(data)
        blocks_needed = (len(data) + BLOCK_SIZE - 1) // BLOCK_SIZE
        
        # Allocate blocks as needed
        for i in range(min(blocks_needed, len(inode.direct_blocks))):
            if inode.direct_blocks[i] == 0:
                block_num = self.allocator.allocate_block()
                if block_num is None:
                    raise Exception("No free blocks available")
                inode.direct_blocks[i] = block_num
                inode.block_count += 1
        
        # Write data to blocks
        for i in range(blocks_needed):
            if i < len(inode.direct_blocks) and inode.direct_blocks[i] != 0:
                offset = i * BLOCK_SIZE
                block_data = data[offset:offset+BLOCK_SIZE]
                if len(block_data) < BLOCK_SIZE:
                    block_data += b'\x00' * (BLOCK_SIZE - len(block_data))
                self.device.write_block(inode.direct_blocks[i], block_data)
        
        inode.modified = int(time.time())
        self._write_allocator()
    
    def _parse_path(self, path):
        """Parse a path into components"""
        parts = [p for p in path.split('/') if p]
        return parts
    
    def _lookup_path(self, path):
        """Look up a path and return (parent_inode_num, filename, entry_inode_num)"""
        if path == '/':
            return None, None, 1
        
        parts = self._parse_path(path)
        current_inode = 1  # Start at root
        
        for i, part in enumerate(parts):
            if current_inode not in self.inodes:
                return None, None, None
            
            inode = self.inodes[current_inode]
            if inode.file_type != FileType.DIRECTORY:
                return None, None, None
            
            # Read directory entries
            dir_data = self._read_inode_data(inode)
            entries = self._parse_directory(dir_data)
            
            # Look for matching entry
            found = False
            for entry in entries:
                if entry.name == part:
                    if i == len(parts) - 1:
                        # This is the target
                        return current_inode, part, entry.inode_num
                    else:
                        # Continue searching
                        current_inode = entry.inode_num
                        found = True
                        break
            
            if not found:
                return current_inode if i == len(parts) - 1 else None, part, None
        
        return None, None, None
    
    def _parse_directory(self, data):
        """Parse directory data into list of DirEntry objects"""
        entries = []
        offset = 0
        
        while offset < len(data):
            if offset + 8 > len(data):
                break
            
            # Check if we've hit padding
            if all(b == 0 for b in data[offset:offset+8]):
                break
            
            entry, size = DirEntry.from_bytes(data[offset:])
            entries.append(entry)
            offset += size
        
        return entries
    
    def _write_directory(self, inode, entries):
        """Write directory entries to inode"""
        data = bytearray()
        for entry in entries:
            data.extend(entry.to_bytes())
        
        self._write_inode_data(inode, bytes(data))
    
    def create_directory(self, path):
        """Create a new directory"""
        parent_inum, name, existing_inum = self._lookup_path(path)
        
        if existing_inum is not None:
            raise Exception(f"Path already exists: {path}")
        
        if parent_inum is None:
            raise Exception(f"Parent directory not found: {path}")
        
        # Allocate new inode
        new_inum = self._allocate_inode()
        if new_inum is None:
            raise Exception("No free inodes")
        
        # Create directory inode
        new_inode = Inode(FileType.DIRECTORY)
        self.inodes[new_inum] = new_inode
        
        # Add entry to parent directory
        parent_inode = self.inodes[parent_inum]
        dir_data = self._read_inode_data(parent_inode)
        entries = self._parse_directory(dir_data)
        entries.append(DirEntry(new_inum, name))
        self._write_directory(parent_inode, entries)
        
        self._write_inodes()
        
        return new_inum
    
    def create_file(self, path):
        """Create a new file"""
        parent_inum, name, existing_inum = self._lookup_path(path)
        
        if existing_inum is not None:
            raise Exception(f"Path already exists: {path}")
        
        if parent_inum is None:
            raise Exception(f"Parent directory not found: {path}")
        
        # Allocate new inode
        new_inum = self._allocate_inode()
        if new_inum is None:
            raise Exception("No free inodes")
        
        # Create file inode
        new_inode = Inode(FileType.REGULAR)
        self.inodes[new_inum] = new_inode
        
        # Add entry to parent directory
        parent_inode = self.inodes[parent_inum]
        dir_data = self._read_inode_data(parent_inode)
        entries = self._parse_directory(dir_data)
        entries.append(DirEntry(new_inum, name))
        self._write_directory(parent_inode, entries)
        
        self._write_inodes()
        
        return new_inum
    
    def write_file(self, path, data):
        """Write data to a file"""
        _, _, inode_num = self._lookup_path(path)
        
        if inode_num is None:
            raise Exception(f"File not found: {path}")
        
        inode = self.inodes[inode_num]
        if inode.file_type != FileType.REGULAR:
            raise Exception(f"Not a regular file: {path}")
        
        self._write_inode_data(inode, data)
        self._write_inodes()
    
    def read_file(self, path):
        """Read data from a file"""
        _, _, inode_num = self._lookup_path(path)
        
        if inode_num is None:
            raise Exception(f"File not found: {path}")
        
        inode = self.inodes[inode_num]
        if inode.file_type != FileType.REGULAR:
            raise Exception(f"Not a regular file: {path}")
        
        inode.accessed = int(time.time())
        self._write_inodes()
        
        return self._read_inode_data(inode)
    
    def list_directory(self, path='/'):
        """List directory contents"""
        if path == '/':
            inode_num = 1
        else:
            _, _, inode_num = self._lookup_path(path)
        
        if inode_num is None:
            raise Exception(f"Directory not found: {path}")
        
        inode = self.inodes[inode_num]
        if inode.file_type != FileType.DIRECTORY:
            raise Exception(f"Not a directory: {path}")
        
        dir_data = self._read_inode_data(inode)
        entries = self._parse_directory(dir_data)
        
        return [entry.name for entry in entries]
    
    def delete_file(self, path):
        """Delete a file or empty directory"""
        parent_inum, name, inode_num = self._lookup_path(path)
        
        if inode_num is None:
            raise Exception(f"Path not found: {path}")
        
        inode = self.inodes[inode_num]
        
        # Free data blocks
        for block_num in inode.direct_blocks:
            if block_num != 0:
                self.allocator.free_block(block_num)
        
        # Remove from parent directory
        parent_inode = self.inodes[parent_inum]
        dir_data = self._read_inode_data(parent_inode)
        entries = self._parse_directory(dir_data)
        entries = [e for e in entries if e.name != name]
        self._write_directory(parent_inode, entries)
        
        # Free inode
        self._free_inode(inode_num)
        
        self._write_allocator()
        self._write_inodes()
    
    def get_file_info(self, path):
        """Get file information"""
        if path == '/':
            inode_num = 1
        else:
            _, _, inode_num = self._lookup_path(path)
        
        if inode_num is None:
            return None
        
        return self.inodes[inode_num]
    
    def get_stats(self):
        """Get filesystem statistics"""
        class Stats:
            pass
        
        stats = Stats()
        stats.total_blocks = self.superblock.total_blocks
        stats.free_blocks = self.allocator.free_blocks()
        stats.total_inodes = self.superblock.inode_count
        stats.used_inodes = sum(1 for used in self.inode_bitmap if used)
        
        return stats
    
    def get_dna_stats(self):
        """Get DNA-specific statistics"""
        return self.device.get_dna_stats()
    
    def tree(self, path='/', prefix='', is_last=True):
        """Generate directory tree view"""
        lines = []
        
        if path == '/':
            lines.append('/')
            inode_num = 1
        else:
            _, name, inode_num = self._lookup_path(path)
            if inode_num is None:
                return [f"Path not found: {path}"]
            
            connector = '└── ' if is_last else '├── '
            lines.append(prefix + connector + name.split('/')[-1])
        
        inode = self.inodes.get(inode_num)
        if inode and inode.file_type == FileType.DIRECTORY:
            dir_data = self._read_inode_data(inode)
            entries = self._parse_directory(dir_data)
            
            extension = '    ' if is_last else '│   '
            new_prefix = prefix + extension
            
            for i, entry in enumerate(entries):
                is_last_entry = (i == len(entries) - 1)
                child_path = f"{path.rstrip('/')}/{entry.name}"
                child_lines = self.tree(child_path, new_prefix, is_last_entry)
                lines.extend(child_lines[1:] if len(child_lines) > 1 else child_lines)
        
        return lines
    
    def close(self):
        """Close the filesystem"""
        self._write_superblock()
        self._write_allocator()
        self._write_inodes()
        self.device.close()


# Compatibility alias
FileSystem = DNAFileSystem