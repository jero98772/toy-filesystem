#!/usr/bin/env python3
"""
DNA Block Device - Stores blocks as DNA sequences (ACGT) in text format
"""

from dna_codec import DNACodec

BLOCK_SIZE = 4096  # 4KB blocks (in binary)
DNA_BLOCK_SEPARATOR = '\n'  # Each block on separate line


class DNABlockDevice:
    """Handles block-level I/O operations using DNA encoding"""
    
    def __init__(self, file_path, block_count, ecc_symbols=10):
        self.file_path = file_path
        self.block_count = block_count
        self.ecc_symbols = ecc_symbols
        self.codec = DNACodec(ecc_symbols)
        self.file = None
        
        # Calculate DNA sequence length for one block
        # Each byte becomes 8 bits, then add ECC, then convert to DNA (2 bits per base)
        self.dna_block_length = None  # Will be calculated from actual data
    
    @classmethod
    def create(cls, path, size_mb, ecc_symbols=10):
        """Create a new DNA block device with specified size"""
        total_size = size_mb * 1024 * 1024
        block_count = total_size // BLOCK_SIZE
        
        device = cls(path, block_count, ecc_symbols)
        
        # Create file and initialize with empty DNA blocks
        with open(path, 'w') as f:
            codec = DNACodec(ecc_symbols)
            empty_block = b'\x00' * BLOCK_SIZE
            empty_dna = codec.encode(empty_block)
            
            # Write all blocks as DNA sequences
            for i in range(block_count):
                f.write(empty_dna)
                if i < block_count - 1:
                    f.write(DNA_BLOCK_SEPARATOR)
        
        device.file = open(path, 'r+')
        device._calculate_block_length()
        return device
    
    @classmethod
    def open(cls, path, ecc_symbols=10):
        """Open an existing DNA block device"""
        device = cls(path, 0, ecc_symbols)
        device.file = open(path, 'r+')
        device._calculate_block_length()
        
        # Count blocks
        device.file.seek(0)
        content = device.file.read()
        blocks = content.split(DNA_BLOCK_SEPARATOR)
        device.block_count = len([b for b in blocks if b.strip()])
        
        return device
    
    def _calculate_block_length(self):
        """Calculate the DNA sequence length for one block"""
        if self.file:
            self.file.seek(0)
            first_line = self.file.readline().strip()
            self.dna_block_length = len(first_line)
            self.file.seek(0)
    
    def _get_block_position(self, block_num):
        """Calculate file position for a given block number"""
        if self.dna_block_length is None:
            self._calculate_block_length()
        
        # Each block is DNA sequence + separator
        chars_per_block = self.dna_block_length + len(DNA_BLOCK_SEPARATOR)
        return block_num * chars_per_block
    
    def read_block(self, block_num):
        """Read a single block and return as binary data"""
        if block_num >= self.block_count:
            return b'\x00' * BLOCK_SIZE
        
        # Seek to block position
        position = self._get_block_position(block_num)
        self.file.seek(position)
        
        # Read DNA sequence
        dna_sequence = self.file.readline().strip()
        
        # Decode DNA to binary
        binary_data = self.codec.decode(dna_sequence)
        
        # Ensure correct size
        if len(binary_data) < BLOCK_SIZE:
            binary_data += b'\x00' * (BLOCK_SIZE - len(binary_data))
        elif len(binary_data) > BLOCK_SIZE:
            binary_data = binary_data[:BLOCK_SIZE]
        
        return binary_data
    
    def write_block(self, block_num, data):
        """Write a single block from binary data"""
        if block_num >= self.block_count:
            return
        
        # Ensure data is correct size
        if len(data) < BLOCK_SIZE:
            data = data + b'\x00' * (BLOCK_SIZE - len(data))
        elif len(data) > BLOCK_SIZE:
            data = data[:BLOCK_SIZE]
        
        # Encode to DNA
        dna_sequence = self.codec.encode(data)
        
        # If this is the first write, calculate block length
        if self.dna_block_length is None:
            self.dna_block_length = len(dna_sequence)
        
        # Seek to block position
        position = self._get_block_position(block_num)
        self.file.seek(position)
        
        # Write DNA sequence
        self.file.write(dna_sequence)
        if block_num < self.block_count - 1:
            self.file.write(DNA_BLOCK_SEPARATOR)
        
        self.file.flush()
    
    def close(self):
        """Close the DNA block device"""
        if self.file:
            self.file.close()
            self.file = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def get_dna_stats(self):
        """Get statistics about DNA storage"""
        if self.dna_block_length is None:
            self._calculate_block_length()
        
        return {
            'binary_block_size': BLOCK_SIZE,
            'dna_block_length': self.dna_block_length,
            'compression_ratio': self.dna_block_length / (BLOCK_SIZE * 4),  # 4 chars per byte in hex
            'ecc_symbols': self.ecc_symbols,
            'correctable_errors': self.ecc_symbols // 2,
            'total_blocks': self.block_count
        }


# Testing
if __name__ == "__main__":
    import os
    
    print("=== Testing DNA Block Device ===\n")
    
    # Create a small test device
    test_file = "/tmp/test_dna.img"
    if os.path.exists(test_file):
        os.remove(test_file)
    
    print("Creating DNA block device (1 MB)...")
    device = DNABlockDevice.create(test_file, 1)
    
    # Get stats
    stats = device.get_dna_stats()
    print(f"\nDNA Storage Statistics:")
    print(f"  Binary block size: {stats['binary_block_size']} bytes")
    print(f"  DNA block length: {stats['dna_block_length']} bases")
    print(f"  ECC symbols: {stats['ecc_symbols']}")
    print(f"  Can correct: {stats['correctable_errors']} errors per block")
    print(f"  Total blocks: {stats['total_blocks']}")
    
    # Test write and read
    print("\nTesting write/read...")
    test_data = b"Hello from DNA storage! " * 100
    test_data = test_data[:BLOCK_SIZE]
    
    device.write_block(5, test_data)
    read_data = device.read_block(5)
    
    print(f"Write successful: {test_data == read_data}")
    print(f"First 50 bytes: {read_data[:50]}")
    
    device.close()
    
    # Show DNA file content (first block)
    print("\nDNA file content (first 200 characters):")
    with open(test_file, 'r') as f:
        content = f.read(200)
        print(content)
        print(f"...(total size: {os.path.getsize(test_file)} bytes)")
    
    print("\n✓ DNA Block Device test complete!")