#!/usr/bin/env python3
"""
File System - Main filesystem implementation
"""

import struct
import time

from tools.block_device import BlockDevice, BLOCK_SIZE
from tools.block_allocator import BlockAllocator
from tools.inode import Inode, FileType, INODE_SIZE, DIRECT_BLOCKS
from tools.directory import DirEntry
from tools.superblock import Superblock


class FileInfo:
    """File information structure"""
    
    def __init__(self, file_type, size, created, modified, accessed):
        self.file_type = file_type
        self.size = size
        self.created = created
        self.modified = modified
        self.accessed = accessed
    
    def __repr__(self):
        type_name = "REGULAR" if self.file_type == FileType.REGULAR else "DIRECTORY"
        return (f"FileInfo(type={type_name}, size={self.size}, "
                f"created={self.created}, modified={self.modified})")


class FsStats:
    """Filesystem statistics"""
    
    def __init__(self, total_blocks, free_blocks, total_inodes, used_inodes):
        self.total_blocks = total_blocks
        self.free_blocks = free_blocks
        self.total_inodes = total_inodes
        self.used_inodes = used_inodes
    
    def __repr__(self):
        return (f"FsStats(blocks: {self.total_blocks - self.free_blocks}/"
                f"{self.total_blocks}, inodes: {self.used_inodes}/"
                f"{self.total_inodes})")


class FileSystem:
    """Main filesystem implementation"""
    
    def __init__(self, device, allocator, superblock, inode_table, next_inode):
        self.device = device
        self.allocator = allocator
        self.superblock = superblock
        self.inode_table = inode_table
        self.next_inode = next_inode
    
    @classmethod
    def create(cls, path, size_mb):
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
        
        root_inode.direct_blocks[0] = root_block
        root_inode.block_count = 1
        
        # Write empty root directory block
        empty_block = bytes(BLOCK_SIZE)
        device.write_block(root_block, empty_block)
        
        # Write inode table
        cls._write_inode_table(device, inode_table)
        
        return cls(device, allocator, superblock, inode_table, next_inode=2)
    
    @classmethod
    def open(cls, path):
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
    def _write_inode_table(device, inode_table):
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
    def _read_inode_table(device):
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
    
    def create_file(self, path):
        """Create a new file"""
        parent_path, filename = self._split_path(path)
        parent_inode_num = self._find_inode(parent_path)
        
        # Check if file already exists
        existing = self._lookup_in_directory(parent_inode_num, filename)
        if existing is not None:
            return
        
        # Create new inode
        inode_num = self.next_inode
        self.next_inode += 1
        
        new_inode = Inode(FileType.REGULAR)
        self.inode_table[inode_num] = new_inode
        
        # Add to parent directory
        self._add_dir_entry(parent_inode_num, filename, inode_num)
        
        # Update on disk
        self._sync()
    
    def create_directory(self, path):
        """Create a new directory"""
        parent_path, dirname = self._split_path(path)
        parent_inode_num = self._find_inode(parent_path)
        
        # Check if directory already exists
        existing = self._lookup_in_directory(parent_inode_num, dirname)
        if existing is not None:
            return
        
        # Allocate block for directory
        dir_block = self.allocator.allocate_block()
        
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
    
    def write_file(self, path, data):
        """Write data to a file"""
        inode_num = self._find_inode(path)
        inode = self.inode_table.get(inode_num)
        
        if inode is None:
            return
        
        if inode.file_type != FileType.REGULAR:
            return
        
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
    
    def read_file(self, path):
        """Read data from a file"""
        inode_num = self._find_inode(path)
        inode = self.inode_table.get(inode_num)
        
        if inode is None:
            return bytes()
        
        if inode.file_type != FileType.REGULAR:
            return bytes()
        
        data = bytearray()
        remaining = inode.size
        
        for i in range(inode.block_count):
            if i >= DIRECT_BLOCKS:
                break
            
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
    
    def list_directory(self, path):
        """List contents of a directory"""
        inode_num = self._find_inode(path)
        inode = self.inode_table.get(inode_num)
        
        if inode is None:
            return []
        
        if inode.file_type != FileType.DIRECTORY:
            return []
        
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
                
                if offset + 8 <= BLOCK_SIZE:
                    entry, size = DirEntry.from_bytes(block_data[offset:])
                    entries.append(entry.name)
                    offset += size
                else:
                    break
        
        return entries
    
    def delete_file(self, path):
        """Delete a file"""
        parent_path, filename = self._split_path(path)
        parent_inode_num = self._find_inode(parent_path)
        file_inode_num = self._lookup_in_directory(parent_inode_num, filename)
        
        if file_inode_num is None:
            return
        
        inode = self.inode_table.get(file_inode_num)
        if inode is None:
            return
        
        # Free blocks
        for i in range(inode.block_count):
            if i < DIRECT_BLOCKS and inode.direct_blocks[i] != 0:
                self.allocator.free_block(inode.direct_blocks[i])
        
        # Remove from inode table
        del self.inode_table[file_inode_num]
        
        # Remove from parent directory
        self._remove_dir_entry(parent_inode_num, filename)
        
        self._sync()
    
    def get_file_info(self, path):
        """Get file information"""
        inode_num = self._find_inode(path)
        inode = self.inode_table.get(inode_num)
        
        if inode is None:
            return None
        
        return FileInfo(
            file_type=inode.file_type,
            size=inode.size,
            created=inode.created,
            modified=inode.modified,
            accessed=inode.accessed
        )
    
    def get_stats(self):
        """Get filesystem statistics"""
        return FsStats(
            total_blocks=self.superblock.total_blocks,
            free_blocks=self.allocator.free_blocks(),
            total_inodes=self.superblock.inode_count,
            used_inodes=len(self.inode_table)
        )
    
    def tree(self, path="/", prefix="", is_last=True, visited=None):
        """Display directory tree structure"""
        if visited is None:
            visited = set()
        
        inode_num = self._find_inode(path)
        if inode_num is None:
            return []
        
        # Cycle detection
        if inode_num in visited:
            connector = "└── " if is_last else "├── "
            return [prefix + connector + "⚠️  [CYCLE DETECTED]"]
        
        visited.add(inode_num)
        
        inode = self.inode_table.get(inode_num)
        if inode is None:
            return []
        
        lines = []
        
        # Get the name of the current directory
        if path == "/":
            name = "/"
        else:
            name = path.split('/')[-1]
        
        # Add current directory/file with icon
        if prefix == "":
            # Root level - no indentation
            if inode.file_type == FileType.DIRECTORY:
                lines.append("📁 " + name)
            else:
                lines.append("📄 " + name)
        else:
            connector = "└── " if is_last else "├── "
            if inode.file_type == FileType.DIRECTORY:
                lines.append(prefix + connector + "📁 " + name)
            else:
                lines.append(prefix + connector + "📄 " + name)
        
        # If it's a directory, process children
        if inode.file_type == FileType.DIRECTORY:
            entries = self.list_directory(path)
            
            for i, entry in enumerate(entries):
                is_last_entry = (i == len(entries) - 1)
                
                # Build child path
                if path == "/":
                    child_path = "/" + entry
                else:
                    child_path = path + "/" + entry
                
                # Build new prefix with TAB for proper indentation
                if prefix == "":
                    new_prefix = "\t"
                else:
                    new_prefix = prefix + "\t"
                
                # Recursively get subtree with visited tracking
                child_lines = self.tree(child_path, new_prefix, is_last_entry, visited.copy())
                lines.extend(child_lines)
        
        return lines
    
    def _find_inode(self, path):
        """Find inode number for a given path"""
        if path == "/":
            return self.superblock.root_inode
        
        parts = [p for p in path.strip('/').split('/') if p]
        current_inode = self.superblock.root_inode
        
        for part in parts:
            current_inode = self._lookup_in_directory(current_inode, part)
            if current_inode is None:
                return None
        
        return current_inode
    
    def _lookup_in_directory(self, dir_inode_num, name):
        """Look up a name in a directory, returns inode number or None"""
        inode = self.inode_table.get(dir_inode_num)
        
        if inode is None:
            return None
        
        if inode.file_type != FileType.DIRECTORY:
            return None
        
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
                
                if offset + 8 <= BLOCK_SIZE:
                    entry, size = DirEntry.from_bytes(block_data[offset:])
                    if entry.name == name:
                        return entry.inode_num
                    offset += size
                else:
                    break
        
        return None
    
    def _add_dir_entry(self, dir_inode_num, name, inode_num):
        """Add an entry to a directory"""
        entry = DirEntry(inode_num, name)
        entry_bytes = entry.to_bytes()
        
        inode = self.inode_table.get(dir_inode_num)
        if inode is None:
            return
        
        # For simplicity, just use the first block
        if inode.block_count == 0:
            # Allocate first block for directory
            new_block = self.allocator.allocate_block()
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
            
            if offset + 8 <= BLOCK_SIZE:
                _, size = DirEntry.from_bytes(bytes(block_data[offset:]))
                offset += size
            else:
                break
        
        if offset + len(entry_bytes) > BLOCK_SIZE:
            return
        
        # Write entry
        block_data[offset:offset+len(entry_bytes)] = entry_bytes
        self.device.write_block(block_num, bytes(block_data))
    
    def _remove_dir_entry(self, dir_inode_num, name):
        """Remove an entry from a directory"""
        inode = self.inode_table.get(dir_inode_num)
        
        if inode is None:
            return
        
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
                
                if offset + 8 <= BLOCK_SIZE:
                    entry, size = DirEntry.from_bytes(bytes(block_data[offset:]))
                    if entry.name != name:
                        entries.append(entry)
                    offset += size
                else:
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
    
    def _split_path(self, path):
        """Split path into parent and filename"""
        path = path.rstrip('/')
        
        if path == "/":
            return None, None
        
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