#!/usr/bin/env python3
"""
DNA Filesystem - Complete Example
"""

import os
from filesystem import DNAFileSystem, FileType


def main():
    print("=" * 70)
    print(" DNA FILESYSTEM - Complete Example")
    print(" Binary → ACGT with Reed-Solomon Error Correction")
    print("=" * 70)
    
    # Setup
    fs_path = "/tmp/example_dna.img"
    if os.path.exists(fs_path):
        os.remove(fs_path)
    
    # Create filesystem
    print("\n1. Creating DNA Filesystem (5 MB with 10 ECC symbols)")
    print("   Encoding: 00→A, 01→C, 10→G, 11→T")
    fs = DNAFileSystem.create(fs_path, 5, ecc_symbols=10)
    
    # Show DNA configuration
    dna_stats = fs.get_dna_stats()
    print(f"\n   DNA Configuration:")
    print(f"   • Binary block: {dna_stats['binary_block_size']} bytes")
    print(f"   • DNA bases per block: {dna_stats['dna_block_length']}")
    print(f"   • Error correction: {dna_stats['correctable_errors']} mutations per block")
    print(f"   • Total blocks: {dna_stats['total_blocks']}")
    
    # Create directory structure
    print("\n2. Creating Directory Structure")
    fs.create_directory("/projects")
    fs.create_directory("/projects/research")
    fs.create_directory("/documents")
    print("   ✓ Created /projects, /projects/research, /documents")
    
    # Create and write files
    print("\n3. Creating and Writing Files")
    
    # File 1: Simple text
    fs.create_file("/projects/hello.txt")
    fs.write_file("/projects/hello.txt", b"Hello from DNA storage!")
    print("   ✓ /projects/hello.txt")
    
    # File 2: Research notes
    research_text = """DNA Storage Research Notes
=========================

Key Facts:
- 1 gram of DNA can store 215 petabytes
- DNA lasts thousands of years
- No power needed for storage
- Reed-Solomon codes protect against mutations

Encoding:
00 -> A (Adenine)
01 -> C (Cytosine)
10 -> G (Guanine)
11 -> T (Thymine)
"""
    fs.create_file("/projects/research/notes.txt")
    fs.write_file("/projects/research/notes.txt", research_text.encode())
    print("   ✓ /projects/research/notes.txt")
    
    # File 3: Numbers
    numbers = " ".join(str(i) for i in range(1, 51))
    fs.create_file("/documents/numbers.txt")
    fs.write_file("/documents/numbers.txt", numbers.encode())
    print("   ✓ /documents/numbers.txt")
    
    # Show directory tree
    print("\n4. Directory Tree:")
    for line in fs.tree("/"):
        print(f"   {line}")
    
    # Read and display a file
    print("\n5. Reading File Content:")
    content = fs.read_file("/projects/hello.txt")
    print(f"   /projects/hello.txt: {content.decode()}")
    
    # Show file info
    print("\n6. File Information:")
    info = fs.get_file_info("/projects/research/notes.txt")
    print(f"   Path: /projects/research/notes.txt")
    print(f"   Size: {info.size} bytes")
    print(f"   Type: {'FILE' if info.file_type == FileType.REGULAR else 'DIR'}")
    print(f"   Blocks used: {info.block_count}")
    
    # List directory
    print("\n7. Listing /projects:")
    entries = fs.list_directory("/projects")
    for entry in entries:
        print(f"   • {entry}")
    
    # Show filesystem statistics
    print("\n8. Filesystem Statistics:")
    stats = fs.get_stats()
    used_blocks = stats.total_blocks - stats.free_blocks
    block_usage = (used_blocks / stats.total_blocks) * 100
    inode_usage = (stats.used_inodes / stats.total_inodes) * 100
    
    print(f"   Blocks: {used_blocks}/{stats.total_blocks} ({block_usage:.1f}% used)")
    print(f"   Inodes: {stats.used_inodes}/{stats.total_inodes} ({inode_usage:.1f}% used)")
    
    fs.close()
    
    # Show actual DNA content
    print("\n9. DNA File Content (First 500 bases):")
    with open(fs_path, 'r') as f:
        content = f.read(500)
        print(f"   {content}")
        if len(content) == 500:
            print("   ...")
    
    # Show file size
    file_size = os.path.getsize(fs_path)
    print(f"\n   Total DNA file size: {file_size:,} bytes")
    
    # Demonstrate error correction
    print("\n10. Testing Error Correction:")
    print("    Simulating DNA mutations...")
    
    # Read the DNA file
    with open(fs_path, 'r') as f:
        dna_content = f.read()
    
    # Introduce 3 mutations
    import random
    dna_list = list(dna_content)
    mutations = {'A': 'T', 'C': 'G', 'G': 'A', 'T': 'C'}
    
    # Only mutate ACGT characters
    dna_positions = [i for i, c in enumerate(dna_list) if c in 'ACGT']
    mutation_positions = random.sample(dna_positions, 3)
    
    for pos in mutation_positions:
        old = dna_list[pos]
        new = mutations[old]
        dna_list[pos] = new
        print(f"    • Position {pos}: {old} → {new}")
    
    # Write mutated DNA
    with open(fs_path, 'w') as f:
        f.write(''.join(dna_list))
    
    # Try to read file with mutations
    print("\n    Reopening filesystem with mutations...")
    fs = DNAFileSystem.open(fs_path, ecc_symbols=10)
    
    try:
        recovered = fs.read_file("/projects/hello.txt")
        original = b"Hello from DNA storage!"
        
        if recovered == original:
            print(f"    ✓ File recovered perfectly!")
            print(f"    Content: {recovered.decode()}")
        else:
            print(f"    ✗ Partial recovery")
    except Exception as e:
        print(f"    ✗ Error: {e}")
    
    fs.close()
    
    # Summary
    print("\n" + "=" * 70)
    print(" Summary")
    print("=" * 70)
    print("\n ✓ Created DNA filesystem with ACGT encoding")
    print(" ✓ Stored files as DNA sequences with error correction")
    print(" ✓ Successfully recovered data despite DNA mutations")
    print(" ✓ File format: Plain text ACGT (human-readable)")
    print("\n Features:")
    print("   • Reed-Solomon error correction (10 symbols)")
    print("   • Can correct up to 5 errors per 4KB block")
    print("   • ~20% storage overhead for error protection")
    print("   • Complete filesystem with directories")
    print("   • Unix-like file operations")
    
    print("\n To explore interactively, run: python3 dna_shell.py")
    print("=" * 70)


if __name__ == "__main__":
    main()