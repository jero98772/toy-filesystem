use std::collections::HashMap;
use std::fs::{File, OpenOptions};
use std::io::{Read, Write, Seek, SeekFrom};
use std::path::Path;

// Constants
const BLOCK_SIZE: usize = 4096; // 4KB blocks
const MAGIC_NUMBER: u32 = 0xDEADBEEF;
const MAX_FILENAME_LEN: usize = 255;
const INODE_SIZE: usize = 128;
const DIRECT_BLOCKS: usize = 12;

// Error types
#[derive(Debug)]
pub enum FsError {
    IoError(std::io::Error),
    InvalidFormat,
    FileNotFound,
    DirectoryNotEmpty,
    NoSpace,
    InvalidPath,
    FileExists,
}

impl From<std::io::Error> for FsError {
    fn from(err: std::io::Error) -> Self {
        FsError::IoError(err)
    }
}

type FsResult<T> = Result<T, FsError>;

// Layer 1: Block Layer - Raw block I/O
pub struct BlockDevice {
    file: File,
    block_count: u32,
}

impl BlockDevice {
    pub fn create(path: &Path, size_mb: u32) -> FsResult<Self> {
        let total_size = (size_mb as u64) * 1024 * 1024;
        let block_count = (total_size / BLOCK_SIZE as u64) as u32;
        
        let file = OpenOptions::new()
            .create(true)
            .write(true)
            .read(true)
            .truncate(true)
            .open(path)?;
        
        // Initialize with zeros
        file.set_len(total_size)?;
        
        Ok(BlockDevice { file, block_count })
    }
    
    pub fn open(path: &Path) -> FsResult<Self> {
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .open(path)?;
        
        let size = file.metadata()?.len();
        let block_count = (size / BLOCK_SIZE as u64) as u32;
        
        Ok(BlockDevice { file, block_count })
    }
    
    pub fn read_block(&mut self, block_num: u32) -> FsResult<[u8; BLOCK_SIZE]> {
        if block_num >= self.block_count {
            return Err(FsError::InvalidFormat);
        }
        
        let offset = (block_num as u64) * (BLOCK_SIZE as u64);
        self.file.seek(SeekFrom::Start(offset))?;
        
        let mut buffer = [0u8; BLOCK_SIZE];
        self.file.read_exact(&mut buffer)?;
        Ok(buffer)
    }
    
    pub fn write_block(&mut self, block_num: u32, data: &[u8; BLOCK_SIZE]) -> FsResult<()> {
        if block_num >= self.block_count {
            return Err(FsError::InvalidFormat);
        }
        
        let offset = (block_num as u64) * (BLOCK_SIZE as u64);
        self.file.seek(SeekFrom::Start(offset))?;
        self.file.write_all(data)?;
        self.file.sync_all()?;
        Ok(())
    }
    
    pub fn block_count(&self) -> u32 {
        self.block_count
    }
}

// Layer 2: Block Allocation - Bitmap-based free block management
pub struct BlockAllocator {
    bitmap: Vec<u8>,
    total_blocks: u32,
}

impl BlockAllocator {
    pub fn new(total_blocks: u32) -> Self {
        let bitmap_size = ((total_blocks + 7) / 8) as usize;
        let mut bitmap = vec![0u8; bitmap_size];
        
        // Mark first few blocks as reserved for metadata
        let reserved_blocks = 10; // Superblock, inode table, etc.
        for i in 0..reserved_blocks.min(total_blocks) {
            Self::set_bit(&mut bitmap, i);
        }
        
        BlockAllocator {
            bitmap,
            total_blocks,
        }
    }
    
    pub fn from_bytes(data: &[u8], total_blocks: u32) -> Self {
        BlockAllocator {
            bitmap: data.to_vec(),
            total_blocks,
        }
    }
    
    pub fn allocate_block(&mut self) -> Option<u32> {
        for i in 0..self.total_blocks {
            if !self.is_allocated(i) {
                self.set_allocated(i, true);
                return Some(i);
            }
        }
        None
    }
    
    pub fn free_block(&mut self, block_num: u32) {
        if block_num < self.total_blocks {
            self.set_allocated(block_num, false);
        }
    }
    
    pub fn is_allocated(&self, block_num: u32) -> bool {
        let byte_idx = (block_num / 8) as usize;
        let bit_idx = block_num % 8;
        
        if byte_idx >= self.bitmap.len() {
            return false;
        }
        
        (self.bitmap[byte_idx] & (1 << bit_idx)) != 0
    }
    
    fn set_allocated(&mut self, block_num: u32, allocated: bool) {
        let byte_idx = (block_num / 8) as usize;
        let bit_idx = block_num % 8;
        
        if byte_idx >= self.bitmap.len() {
            return;
        }
        
        if allocated {
            self.bitmap[byte_idx] |= 1 << bit_idx;
        } else {
            self.bitmap[byte_idx] &= !(1 << bit_idx);
        }
    }
    
    fn set_bit(bitmap: &mut [u8], bit_num: u32) {
        let byte_idx = (bit_num / 8) as usize;
        let bit_idx = bit_num % 8;
        
        if byte_idx < bitmap.len() {
            bitmap[byte_idx] |= 1 << bit_idx;
        }
    }
    
    pub fn to_bytes(&self) -> &[u8] {
        &self.bitmap
    }
    
    pub fn free_blocks(&self) -> u32 {
        let mut free = 0;
        for i in 0..self.total_blocks {
            if !self.is_allocated(i) {
                free += 1;
            }
        }
        free
    }
}

// Layer 3: Inode Layer - File metadata and block pointers
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum FileType {
    Regular = 1,
    Directory = 2,
}

#[derive(Debug, Clone)]
pub struct Inode {
    pub file_type: FileType,
    pub size: u32,
    pub block_count: u32,
    pub direct_blocks: [u32; DIRECT_BLOCKS],
    pub indirect_block: u32,
    pub double_indirect_block: u32,
    pub created: u64,
    pub modified: u64,
    pub accessed: u64,
}

impl Inode {
    pub fn new(file_type: FileType) -> Self {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();
        
        Inode {
            file_type,
            size: 0,
            block_count: 0,
            direct_blocks: [0; DIRECT_BLOCKS],
            indirect_block: 0,
            double_indirect_block: 0,
            created: now,
            modified: now,
            accessed: now,
        }
    }
    
    pub fn from_bytes(data: &[u8]) -> FsResult<Self> {
        if data.len() < INODE_SIZE {
            return Err(FsError::InvalidFormat);
        }
        
        let file_type = match data[0] {
            1 => FileType::Regular,
            2 => FileType::Directory,
            _ => return Err(FsError::InvalidFormat),
        };
        
        let size = u32::from_le_bytes([data[4], data[5], data[6], data[7]]);
        let block_count = u32::from_le_bytes([data[8], data[9], data[10], data[11]]);
        
        let mut direct_blocks = [0u32; DIRECT_BLOCKS];
        for i in 0..DIRECT_BLOCKS {
            let offset = 12 + i * 4;
            direct_blocks[i] = u32::from_le_bytes([
                data[offset], data[offset + 1], data[offset + 2], data[offset + 3]
            ]);
        }
        
        let indirect_block = u32::from_le_bytes([data[60], data[61], data[62], data[63]]);
        let double_indirect_block = u32::from_le_bytes([data[64], data[65], data[66], data[67]]);
        
        let created = u64::from_le_bytes([
            data[68], data[69], data[70], data[71], data[72], data[73], data[74], data[75]
        ]);
        let modified = u64::from_le_bytes([
            data[76], data[77], data[78], data[79], data[80], data[81], data[82], data[83]
        ]);
        let accessed = u64::from_le_bytes([
            data[84], data[85], data[86], data[87], data[88], data[89], data[90], data[91]
        ]);
        
        Ok(Inode {
            file_type,
            size,
            block_count,
            direct_blocks,
            indirect_block,
            double_indirect_block,
            created,
            modified,
            accessed,
        })
    }
    
    pub fn to_bytes(&self) -> [u8; INODE_SIZE] {
        let mut data = [0u8; INODE_SIZE];
        
        data[0] = self.file_type as u8;
        data[4..8].copy_from_slice(&self.size.to_le_bytes());
        data[8..12].copy_from_slice(&self.block_count.to_le_bytes());
        
        for i in 0..DIRECT_BLOCKS {
            let offset = 12 + i * 4;
            data[offset..offset + 4].copy_from_slice(&self.direct_blocks[i].to_le_bytes());
        }
        
        data[60..64].copy_from_slice(&self.indirect_block.to_le_bytes());
        data[64..68].copy_from_slice(&self.double_indirect_block.to_le_bytes());
        data[68..76].copy_from_slice(&self.created.to_le_bytes());
        data[76..84].copy_from_slice(&self.modified.to_le_bytes());
        data[84..92].copy_from_slice(&self.accessed.to_le_bytes());
        
        data
    }
}

// Directory entry structure
#[derive(Debug, Clone)]
pub struct DirEntry {
    pub inode_num: u32,
    pub name: String,
}

impl DirEntry {
    pub fn new(inode_num: u32, name: String) -> Self {
        DirEntry { inode_num, name }
    }
    
    pub fn from_bytes(data: &[u8]) -> FsResult<(Self, usize)> {
        if data.len() < 8 {
            return Err(FsError::InvalidFormat);
        }
        
        let inode_num = u32::from_le_bytes([data[0], data[1], data[2], data[3]]);
        let name_len = u32::from_le_bytes([data[4], data[5], data[6], data[7]]) as usize;
        
        if data.len() < 8 + name_len {
            return Err(FsError::InvalidFormat);
        }
        
        let name = String::from_utf8_lossy(&data[8..8 + name_len]).to_string();
        let total_size = 8 + name_len;
        
        Ok((DirEntry::new(inode_num, name), total_size))
    }
    
    pub fn to_bytes(&self) -> Vec<u8> {
        let mut data = Vec::new();
        data.extend_from_slice(&self.inode_num.to_le_bytes());
        data.extend_from_slice(&(self.name.len() as u32).to_le_bytes());
        data.extend_from_slice(self.name.as_bytes());
        data
    }
}

// Superblock structure
#[derive(Debug)]
pub struct Superblock {
    pub magic: u32,
    pub block_size: u32,
    pub total_blocks: u32,
    pub inode_count: u32,
    pub free_blocks: u32,
    pub root_inode: u32,
}

impl Superblock {
    pub fn new(total_blocks: u32, inode_count: u32) -> Self {
        Superblock {
            magic: MAGIC_NUMBER,
            block_size: BLOCK_SIZE as u32,
            total_blocks,
            inode_count,
            free_blocks: total_blocks - 10, // Reserve first 10 blocks
            root_inode: 1, // Root directory is inode 1
        }
    }
    
    pub fn from_bytes(data: &[u8]) -> FsResult<Self> {
        if data.len() < 24 {
            return Err(FsError::InvalidFormat);
        }
        
        let magic = u32::from_le_bytes([data[0], data[1], data[2], data[3]]);
        if magic != MAGIC_NUMBER {
            return Err(FsError::InvalidFormat);
        }
        
        let block_size = u32::from_le_bytes([data[4], data[5], data[6], data[7]]);
        let total_blocks = u32::from_le_bytes([data[8], data[9], data[10], data[11]]);
        let inode_count = u32::from_le_bytes([data[12], data[13], data[14], data[15]]);
        let free_blocks = u32::from_le_bytes([data[16], data[17], data[18], data[19]]);
        let root_inode = u32::from_le_bytes([data[20], data[21], data[22], data[23]]);
        
        Ok(Superblock {
            magic,
            block_size,
            total_blocks,
            inode_count,
            free_blocks,
            root_inode,
        })
    }
    
    pub fn to_bytes(&self) -> [u8; BLOCK_SIZE] {
        let mut data = [0u8; BLOCK_SIZE];
        
        data[0..4].copy_from_slice(&self.magic.to_le_bytes());
        data[4..8].copy_from_slice(&self.block_size.to_le_bytes());
        data[8..12].copy_from_slice(&self.total_blocks.to_le_bytes());
        data[12..16].copy_from_slice(&self.inode_count.to_le_bytes());
        data[16..20].copy_from_slice(&self.free_blocks.to_le_bytes());
        data[20..24].copy_from_slice(&self.root_inode.to_le_bytes());
        
        data
    }
}

// Layer 4: File System - High-level file operations
pub struct ToyFileSystem {
    device: BlockDevice,
    allocator: BlockAllocator,
    superblock: Superblock,
    inode_table: HashMap<u32, Inode>,
    next_inode: u32,
}

impl ToyFileSystem {
    pub fn create(path: &Path, size_mb: u32) -> FsResult<Self> {
        let mut device = BlockDevice::create(path, size_mb)?;
        let total_blocks = device.block_count();
        
        // Initialize allocator
        let mut allocator = BlockAllocator::new(total_blocks);
        
        // Create superblock
        let inode_count = 1000; // Support up to 1000 files/directories
        let superblock = Superblock::new(total_blocks, inode_count);
        
        // Write superblock
        device.write_block(0, &superblock.to_bytes())?;
        
        // Write bitmap
        let bitmap_data = allocator.to_bytes();
        let mut bitmap_block = [0u8; BLOCK_SIZE];
        let copy_len = bitmap_data.len().min(BLOCK_SIZE);
        bitmap_block[..copy_len].copy_from_slice(&bitmap_data[..copy_len]);
        device.write_block(1, &bitmap_block)?;
        
        // Create root directory
        let mut inode_table = HashMap::new();
        let root_inode = Inode::new(FileType::Directory);
        inode_table.insert(1, root_inode);
        
        // Initialize empty root directory
        let root_block = allocator.allocate_block().ok_or(FsError::NoSpace)?;
        let root_inode = inode_table.get_mut(&1).unwrap();
        root_inode.direct_blocks[0] = root_block;
        root_inode.block_count = 1;
        
        // Write empty root directory block
        let empty_block = [0u8; BLOCK_SIZE];
        device.write_block(root_block, &empty_block)?;
        
        // Write inode table
        Self::write_inode_table(&mut device, &inode_table)?;
        
        Ok(ToyFileSystem {
            device,
            allocator,
            superblock,
            inode_table,
            next_inode: 2,
        })
    }
    
    pub fn open(path: &Path) -> FsResult<Self> {
        let mut device = BlockDevice::open(path)?;
        
        // Read superblock
        let superblock_data = device.read_block(0)?;
        let superblock = Superblock::from_bytes(&superblock_data)?;
        
        // Read bitmap
        let bitmap_data = device.read_block(1)?;
        let allocator = BlockAllocator::from_bytes(&bitmap_data, superblock.total_blocks);
        
        // Read inode table
        let inode_table = Self::read_inode_table(&mut device)?;
        
        let next_inode = inode_table.keys().max().unwrap_or(&1) + 1;
        
        Ok(ToyFileSystem {
            device,
            allocator,
            superblock,
            inode_table,
            next_inode,
        })
    }
    
    fn write_inode_table(device: &mut BlockDevice, inode_table: &HashMap<u32, Inode>) -> FsResult<()> {
        let mut block_data = [0u8; BLOCK_SIZE];
        let mut offset = 0;
        
        for (&inode_num, inode) in inode_table {
            let inode_data = inode.to_bytes();
            
            // Write inode number
            if offset + 4 + INODE_SIZE > BLOCK_SIZE {
                device.write_block(2, &block_data)?;
                block_data = [0u8; BLOCK_SIZE];
                offset = 0;
            }
            
            block_data[offset..offset + 4].copy_from_slice(&inode_num.to_le_bytes());
            block_data[offset + 4..offset + 4 + INODE_SIZE].copy_from_slice(&inode_data);
            offset += 4 + INODE_SIZE;
        }
        
        if offset > 0 {
            device.write_block(2, &block_data)?;
        }
        
        Ok(())
    }
    
    fn read_inode_table(device: &mut BlockDevice) -> FsResult<HashMap<u32, Inode>> {
        let mut inode_table = HashMap::new();
        let block_data = device.read_block(2)?;
        
        let mut offset = 0;
        while offset + 4 + INODE_SIZE <= BLOCK_SIZE {
            let inode_num = u32::from_le_bytes([
                block_data[offset],
                block_data[offset + 1],
                block_data[offset + 2],
                block_data[offset + 3],
            ]);
            
            if inode_num == 0 {
                break;
            }
            
            let inode_data = &block_data[offset + 4..offset + 4 + INODE_SIZE];
            let inode = Inode::from_bytes(inode_data)?;
            inode_table.insert(inode_num, inode);
            
            offset += 4 + INODE_SIZE;
        }
        
        Ok(inode_table)
    }
    
    pub fn create_file(&mut self, path: &str) -> FsResult<()> {
        let path_parts = self.split_path(path)?;
        let parent_path = path_parts.0;
        let filename = path_parts.1;
        let parent_inode_num = self.find_inode(&parent_path)?;
        
        // Check if file already exists
        if self.lookup_in_directory(parent_inode_num, &filename).is_ok() {
            return Err(FsError::FileExists);
        }
        
        // Create new inode
        let inode_num = self.next_inode;
        self.next_inode += 1;
        
        let new_inode = Inode::new(FileType::Regular);
        self.inode_table.insert(inode_num, new_inode);
        
        // Add to parent directory
        self.add_dir_entry(parent_inode_num, &filename, inode_num)?;
        
        // Update on disk
        self.sync()?;
        
        Ok(())
    }
    
    pub fn create_directory(&mut self, path: &str) -> FsResult<()> {
        let path_parts = self.split_path(path)?;
        let parent_path = path_parts.0;
        let dirname = path_parts.1;
        let parent_inode_num = self.find_inode(&parent_path)?;
        
        // Check if directory already exists
        if self.lookup_in_directory(parent_inode_num, &dirname).is_ok() {
            return Err(FsError::FileExists);
        }
        
        // Allocate block for directory
        let dir_block = self.allocator.allocate_block().ok_or(FsError::NoSpace)?;
        
        // Create new inode
        let inode_num = self.next_inode;
        self.next_inode += 1;
        
        let mut new_inode = Inode::new(FileType::Directory);
        new_inode.direct_blocks[0] = dir_block;
        new_inode.block_count = 1;
        
        self.inode_table.insert(inode_num, new_inode);
        
        // Initialize empty directory block
        let empty_block = [0u8; BLOCK_SIZE];
        self.device.write_block(dir_block, &empty_block)?;
        
        // Add to parent directory
        self.add_dir_entry(parent_inode_num, &dirname, inode_num)?;
        
        // Update on disk
        self.sync()?;
        
        Ok(())
    }
    
    pub fn write_file(&mut self, path: &str, data: &[u8]) -> FsResult<()> {
        let inode_num = self.find_inode(path)?;
        let inode = self.inode_table.get_mut(&inode_num).ok_or(FsError::FileNotFound)?;
        
        if inode.file_type != FileType::Regular {
            return Err(FsError::InvalidPath);
        }
        
        // Free existing blocks
        for i in 0..inode.block_count as usize {
            if i < DIRECT_BLOCKS && inode.direct_blocks[i] != 0 {
                self.allocator.free_block(inode.direct_blocks[i]);
                inode.direct_blocks[i] = 0;
            }
        }
        
        // Calculate blocks needed
        let blocks_needed = (data.len() + BLOCK_SIZE - 1) / BLOCK_SIZE;
        
        // Allocate and write blocks
        let mut written = 0;
        for i in 0..blocks_needed.min(DIRECT_BLOCKS) {
            let block = self.allocator.allocate_block().ok_or(FsError::NoSpace)?;
            inode.direct_blocks[i] = block;
            
            let mut block_data = [0u8; BLOCK_SIZE];
            let to_write = (data.len() - written).min(BLOCK_SIZE);
            block_data[..to_write].copy_from_slice(&data[written..written + to_write]);
            
            self.device.write_block(block, &block_data)?;
            written += to_write;
        }
        
        inode.size = data.len() as u32;
        inode.block_count = blocks_needed as u32;
        inode.modified = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();
        
        self.sync()?;
        Ok(())
    }
    
    pub fn read_file(&mut self, path: &str) -> FsResult<Vec<u8>> {
        let inode_num = self.find_inode(path)?;
        let inode = self.inode_table.get(&inode_num).ok_or(FsError::FileNotFound)?;
        
        if inode.file_type != FileType::Regular {
            return Err(FsError::InvalidPath);
        }
        
        let mut data = Vec::new();
        let mut remaining = inode.size as usize;
        
        for i in 0..inode.block_count as usize {
            if i >= DIRECT_BLOCKS {
                break; // TODO: Implement indirect blocks
            }
            
            let block_num = inode.direct_blocks[i];
            if block_num == 0 {
                break;
            }
            
            let block_data = self.device.read_block(block_num)?;
            let to_read = remaining.min(BLOCK_SIZE);
            data.extend_from_slice(&block_data[..to_read]);
            remaining -= to_read;
            
            if remaining == 0 {
                break;
            }
        }
        
        Ok(data)
    }
    
    pub fn list_directory(&mut self, path: &str) -> FsResult<Vec<String>> {
        let inode_num = self.find_inode(path)?;
        let inode = self.inode_table.get(&inode_num).ok_or(FsError::FileNotFound)?;
        
        if inode.file_type != FileType::Directory {
            return Err(FsError::InvalidPath);
        }
        
        let mut entries = Vec::new();
        
        // Read directory blocks
        for i in 0..inode.block_count as usize {
            if i >= DIRECT_BLOCKS {
                break;
            }
            
            let block_num = inode.direct_blocks[i];
            if block_num == 0 {
                break;
            }
            
            let block_data = self.device.read_block(block_num)?;
            let mut offset = 0;
            
            while offset < BLOCK_SIZE {
                if block_data[offset] == 0 {
                    break;
                }
                
                match DirEntry::from_bytes(&block_data[offset..]) {
                    Ok((entry, size)) => {
                        entries.push(entry.name);
                        offset += size;
                    }
                    Err(_) => break,
                }
            }
        }
        
        Ok(entries)
    }
    
    fn find_inode(&mut self, path: &str) -> FsResult<u32> {
        if path == "/" {
            return Ok(self.superblock.root_inode);
        }
        
        let parts: Vec<&str> = path.trim_start_matches('/').split('/').collect();
        let mut current_inode = self.superblock.root_inode;
        
        for part in parts {
            if part.is_empty() {
                continue;
            }
            current_inode = self.lookup_in_directory(current_inode, part)?;
        }
        
        Ok(current_inode)
    }
    
    fn lookup_in_directory(&mut self, dir_inode_num: u32, name: &str) -> FsResult<u32> {
        let inode = self.inode_table.get(&dir_inode_num).ok_or(FsError::FileNotFound)?;
        
        if inode.file_type != FileType::Directory {
            return Err(FsError::InvalidPath);
        }
        
        for i in 0..inode.block_count as usize {
            if i >= DIRECT_BLOCKS {
                break;
            }
            
            let block_num = inode.direct_blocks[i];
            if block_num == 0 {
                continue;
            }
            
            let block_data = self.device.read_block(block_num)?;
            let mut offset = 0;
            
            while offset < BLOCK_SIZE {
                if block_data[offset] == 0 {
                    break;
                }
                
                match DirEntry::from_bytes(&block_data[offset..]) {
                    Ok((entry, size)) => {
                        if entry.name == name {
                            return Ok(entry.inode_num);
                        }
                        offset += size;
                    }
                    Err(_) => break,
                }
            }
        }
        
        Err(FsError::FileNotFound)
    }
    
    fn add_dir_entry(&mut self, dir_inode_num: u32, name: &str, inode_num: u32) -> FsResult<()> {
        let entry = DirEntry::new(inode_num, name.to_string());
        let entry_bytes = entry.to_bytes();
        
        let inode = self.inode_table.get_mut(&dir_inode_num).ok_or(FsError::FileNotFound)?;
        
        // For simplicity, just use the first block
        let block_num = if inode.block_count == 0 {
            // Allocate first block for directory
            let new_block = self.allocator.allocate_block().ok_or(FsError::NoSpace)?;
            inode.direct_blocks[0] = new_block;
            inode.block_count = 1;
            new_block
        } else {
            inode.direct_blocks[0]
        };
        
        let mut block_data = self.device.read_block(block_num)?;
        
        // Find space for new entry
        let mut offset = 0;
        while offset < BLOCK_SIZE {
            if block_data[offset] == 0 {
                break;
            }
            
            match DirEntry::from_bytes(&block_data[offset..]) {
                Ok((_, size)) => offset += size,
                Err(_) => break,
            }
        }
        
        if offset + entry_bytes.len() > BLOCK_SIZE {
            return Err(FsError::NoSpace);
        }
        
        // Write entry
        block_data[offset..offset + entry_bytes.len()].copy_from_slice(&entry_bytes);
        self.device.write_block(block_num, &block_data)?;
        
        Ok(())
    }
    
    fn split_path(&self, path: &str) -> FsResult<(String, String)> {
        let path = path.trim_end_matches('/');
        
        if path == "/" {
            return Err(FsError::InvalidPath);
        }
        
        if let Some(pos) = path.rfind('/') {
            let parent = if pos == 0 { "/" } else { &path[..pos] };
            let filename = &path[pos + 1..];
            Ok((parent.to_string(), filename.to_string()))
        } else {
            Ok(("/".to_string(), path.to_string()))
        }
    }
    
    fn sync(&mut self) -> FsResult<()> {
        // Update superblock
        self.superblock.free_blocks = self.allocator.free_blocks();
        self.device.write_block(0, &self.superblock.to_bytes())?;
        
        // Update bitmap
        let bitmap_data = self.allocator.to_bytes();
        let mut bitmap_block = [0u8; BLOCK_SIZE];
        let copy_len = bitmap_data.len().min(BLOCK_SIZE);
        bitmap_block[..copy_len].copy_from_slice(&bitmap_data[..copy_len]);
        self.device.write_block(1, &bitmap_block)?;
        
        // Update inode table
        Self::write_inode_table(&mut self.device, &self.inode_table)?;
        
        Ok(())
    }
    
    pub fn delete_file(&mut self, path: &str) -> FsResult<()> {
        let path_parts = self.split_path(path)?;
        let parent_path = path_parts.0;
        let filename = path_parts.1;
        let parent_inode_num = self.find_inode(&parent_path)?;
        let file_inode_num = self.lookup_in_directory(parent_inode_num, &filename)?;
        
        let inode = self.inode_table.get(&file_inode_num).ok_or(FsError::FileNotFound)?;
        
        // Free blocks
        let blocks_to_free: Vec<u32> = (0..inode.block_count as usize)
            .filter_map(|i| {
                if i < DIRECT_BLOCKS && inode.direct_blocks[i] != 0 {
                    Some(inode.direct_blocks[i])
                } else {
                    None
                }
            })
            .collect();
        
        for block in blocks_to_free {
            self.allocator.free_block(block);
        }
        
        // Remove from inode table
        self.inode_table.remove(&file_inode_num);
        
        // Remove from parent directory
        self.remove_dir_entry(parent_inode_num, &filename)?;
        
        self.sync()?;
        Ok(())
    }
    
    fn remove_dir_entry(&mut self, dir_inode_num: u32, name: &str) -> FsResult<()> {
        let inode = self.inode_table.get(&dir_inode_num).ok_or(FsError::FileNotFound)?;
        
        for i in 0..inode.block_count as usize {
            if i >= DIRECT_BLOCKS {
                break;
            }
            
            let block_num = inode.direct_blocks[i];
            if block_num == 0 {
                continue;
            }
            
            let mut block_data = self.device.read_block(block_num)?;
            let mut entries = Vec::new();
            let mut offset = 0;
            
            // Parse all entries
            while offset < BLOCK_SIZE {
                if block_data[offset] == 0 {
                    break;
                }
                
                match DirEntry::from_bytes(&block_data[offset..]) {
                    Ok((entry, size)) => {
                        if entry.name != name {
                            entries.push(entry);
                        }
                        offset += size;
                    }
                    Err(_) => break,
                }
            }
            
            // Rewrite block without the deleted entry
            block_data = [0u8; BLOCK_SIZE];
            let mut write_offset = 0;
            
            for entry in entries {
                let entry_bytes = entry.to_bytes();
                if write_offset + entry_bytes.len() <= BLOCK_SIZE {
                    block_data[write_offset..write_offset + entry_bytes.len()]
                        .copy_from_slice(&entry_bytes);
                    write_offset += entry_bytes.len();
                }
            }
            
            self.device.write_block(block_num, &block_data)?;
            return Ok(());
        }
        
        Err(FsError::FileNotFound)
    }
    
    pub fn get_file_info(&mut self, path: &str) -> FsResult<FileInfo> {
        let inode_num = self.find_inode(path)?;
        let inode = self.inode_table.get(&inode_num).ok_or(FsError::FileNotFound)?;
        
        Ok(FileInfo {
            file_type: inode.file_type,
            size: inode.size,
            created: inode.created,
            modified: inode.modified,
            accessed: inode.accessed,
        })
    }
    
    pub fn get_stats(&self) -> FsStats {
        FsStats {
            total_blocks: self.superblock.total_blocks,
            free_blocks: self.allocator.free_blocks(),
            total_inodes: self.superblock.inode_count,
            used_inodes: self.inode_table.len() as u32,
        }
    }
}

#[derive(Debug)]
pub struct FileInfo {
    pub file_type: FileType,
    pub size: u32,
    pub created: u64,
    pub modified: u64,
    pub accessed: u64,
}

#[derive(Debug)]
pub struct FsStats {
    pub total_blocks: u32,
    pub free_blocks: u32,
    pub total_inodes: u32,
    pub used_inodes: u32,
}

// Example usage and tests
#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn test_filesystem_operations() -> FsResult<()> {
        let img_path = Path::new("test_filesystem.img");
        
        // Clean up any existing test file
        let _ = fs::remove_file(img_path);
        
        // Create filesystem
        let mut fs = ToyFileSystem::create(img_path, 10)?; // 10MB
        
        // Create directories
        fs.create_directory("/home")?;
        fs.create_directory("/home/user")?;
        
        // Create files
        fs.create_file("/home/user/hello.txt")?;
        fs.write_file("/home/user/hello.txt", b"Hello, File System!")?;
        
        fs.create_file("/home/user/data.bin")?;
        let test_data = vec![1, 2, 3, 4, 5, 42, 100, 255];
        fs.write_file("/home/user/data.bin", &test_data)?;
        
        // Read files
        let content = fs.read_file("/home/user/hello.txt")?;
        assert_eq!(content, b"Hello, File System!");
        
        let data = fs.read_file("/home/user/data.bin")?;
        assert_eq!(data, test_data);
        
        // List directories
        let root_files = fs.list_directory("/")?;
        println!("Root directory: {:?}", root_files);
        
        let home_files = fs.list_directory("/home")?;
        println!("Home directory: {:?}", home_files);
        
        let user_files = fs.list_directory("/home/user")?;
        println!("User directory: {:?}", user_files);
        
        // Get file info
        let info = fs.get_file_info("/home/user/hello.txt")?;
        println!("File info: {:?}", info);
        
        // Get filesystem stats
        let stats = fs.get_stats();
        println!("Filesystem stats: {:?}", stats);
        
        // Test persistence - close and reopen
        drop(fs);
        
        let mut fs2 = ToyFileSystem::open(img_path)?;
        let content2 = fs2.read_file("/home/user/hello.txt")?;
        assert_eq!(content2, b"Hello, File System!");
        
        // Clean up
        let _ = fs::remove_file(img_path);
        
        Ok(())
    }
}

// CLI interface for interacting with the filesystem
pub fn main() {
    use std::env;
    use std::io::{self, Write};
    
    let args: Vec<String> = env::args().collect();
    
    if args.len() < 2 {
        println!("Usage: {} <command> [args...]", args[0]);
        println!("Commands:");
        println!("  create <img_file> <size_mb> - Create new filesystem");
        println!("  mount <img_file> - Mount existing filesystem (interactive)");
        return;
    }
    
    match args[1].as_str() {
        "create" => {
            if args.len() != 4 {
                println!("Usage: {} create <img_file> <size_mb>", args[0]);
                return;
            }
            
            let img_path = Path::new(&args[2]);
            let size_mb: u32 = args[3].parse().unwrap_or_else(|_| {
                eprintln!("Invalid size: {}", args[3]);
                std::process::exit(1);
            });
            
            match ToyFileSystem::create(img_path, size_mb) {
                Ok(_) => println!("Created filesystem: {}", args[2]),
                Err(e) => eprintln!("Error creating filesystem: {:?}", e),
            }
        }
        "mount" => {
            if args.len() != 3 {
                println!("Usage: {} mount <img_file>", args[0]);
                return;
            }
            
            let img_path = Path::new(&args[2]);
            let mut fs = match ToyFileSystem::open(img_path) {
                Ok(fs) => fs,
                Err(e) => {
                    eprintln!("Error opening filesystem: {:?}", e);
                    return;
                }
            };
            
            println!("Mounted filesystem: {}", args[2]);
            println!("Interactive shell - type 'help' for commands, 'quit' to exit");
            
            loop {
                print!("> ");
                io::stdout().flush().unwrap();
                
                let mut input = String::new();
                if io::stdin().read_line(&mut input).unwrap() == 0 {
                    break;
                }
                
                let cmd_parts: Vec<&str> = input.trim().split_whitespace().collect();
                if cmd_parts.is_empty() {
                    continue;
                }
                
                match cmd_parts[0] {
                    "help" => {
                        println!("Commands:");
                        println!("  ls <path>        - List directory");
                        println!("  mkdir <path>     - Create directory");
                        println!("  touch <path>     - Create empty file");
                        println!("  write <path> <text> - Write text to file");
                        println!("  read <path>      - Read file content");
                        println!("  rm <path>        - Delete file");
                        println!("  info <path>      - Show file info");
                        println!("  stats            - Show filesystem statistics");
                        println!("  quit             - Exit");
                    }
                    "ls" => {
                        let path = cmd_parts.get(1).unwrap_or(&"/");
                        match fs.list_directory(path) {
                            Ok(entries) => {
                                for entry in entries {
                                    println!("  {}", entry);
                                }
                            }
                            Err(e) => println!("Error: {:?}", e),
                        }
                    }
                    "mkdir" => {
                        if cmd_parts.len() != 2 {
                            println!("Usage: mkdir <path>");
                            continue;
                        }
                        match fs.create_directory(cmd_parts[1]) {
                            Ok(_) => println!("Created directory: {}", cmd_parts[1]),
                            Err(e) => println!("Error: {:?}", e),
                        }
                    }
                    "touch" => {
                        if cmd_parts.len() != 2 {
                            println!("Usage: touch <path>");
                            continue;
                        }
                        match fs.create_file(cmd_parts[1]) {
                            Ok(_) => println!("Created file: {}", cmd_parts[1]),
                            Err(e) => println!("Error: {:?}", e),
                        }
                    }
                    "write" => {
                        if cmd_parts.len() < 3 {
                            println!("Usage: write <path> <text>");
                            continue;
                        }
                        let text = cmd_parts[2..].join(" ");
                        match fs.write_file(cmd_parts[1], text.as_bytes()) {
                            Ok(_) => println!("Wrote to file: {}", cmd_parts[1]),
                            Err(e) => println!("Error: {:?}", e),
                        }
                    }
                    "read" => {
                        if cmd_parts.len() != 2 {
                            println!("Usage: read <path>");
                            continue;
                        }
                        match fs.read_file(cmd_parts[1]) {
                            Ok(data) => {
                                match String::from_utf8(data.clone()) {
                                    Ok(text) => println!("{}", text),
                                    Err(_) => println!("Binary data (length: {} bytes)", data.len()),
                                }
                            }
                            Err(e) => println!("Error: {:?}", e),
                        }
                    }
                    "rm" => {
                        if cmd_parts.len() != 2 {
                            println!("Usage: rm <path>");
                            continue;
                        }
                        match fs.delete_file(cmd_parts[1]) {
                            Ok(_) => println!("Deleted: {}", cmd_parts[1]),
                            Err(e) => println!("Error: {:?}", e),
                        }
                    }
                    "info" => {
                        if cmd_parts.len() != 2 {
                            println!("Usage: info <path>");
                            continue;
                        }
                        match fs.get_file_info(cmd_parts[1]) {
                            Ok(info) => {
                                println!("Type: {:?}", info.file_type);
                                println!("Size: {} bytes", info.size);
                                println!("Created: {}", info.created);
                                println!("Modified: {}", info.modified);
                                println!("Accessed: {}", info.accessed);
                            }
                            Err(e) => println!("Error: {:?}", e),
                        }
                    }
                    "stats" => {
                        let stats = fs.get_stats();
                        println!("Total blocks: {}", stats.total_blocks);
                        println!("Free blocks: {}", stats.free_blocks);
                        println!("Used blocks: {}", stats.total_blocks - stats.free_blocks);
                        println!("Total inodes: {}", stats.total_inodes);
                        println!("Used inodes: {}", stats.used_inodes);
                        println!("Free inodes: {}", stats.total_inodes - stats.used_inodes);
                    }
                    "quit" => break,
                    _ => println!("Unknown command: {}. Type 'help' for available commands.", cmd_parts[0]),
                }
            }
        }
        _ => {
            println!("Unknown command: {}", args[1]);
            println!("Use 'create' or 'mount'");
        }
    }
}