#!/usr/bin/env python3
"""
Interactive shell for the DNA File System
"""

from filesystem import DNAFileSystem, FileType


def shell():
    """Interactive DNA filesystem shell"""
    print("=" * 60)
    print("DNA FILESYSTEM SHELL")
    print("Storage encoding: ACGT with Reed-Solomon error correction")
    print("=" * 60)
    
    # Get filesystem path and action
    print("\nWhat would you like to do?")
    print("1. Create new DNA filesystem")
    print("2. Mount existing DNA filesystem")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "1":
        img_path = input("Enter image file path (e.g., dna_disk.img): ").strip()
        size_mb = input("Enter size in MB: ").strip()
        ecc_symbols = input("Enter ECC symbols (default 10, press Enter): ").strip()
        
        size_mb = int(size_mb)
        ecc_symbols = int(ecc_symbols) if ecc_symbols else 10
        
        print(f"\nCreating DNA filesystem at {img_path} with size {size_mb}MB...")
        print(f"Error correction: {ecc_symbols} symbols (can correct {ecc_symbols//2} errors)")
        fs = DNAFileSystem.create(img_path, size_mb, ecc_symbols)
        print(f"✓ DNA Filesystem created successfully!")
        
        # Show DNA stats
        dna_stats = fs.get_dna_stats()
        print(f"\nDNA Storage Configuration:")
        print(f"  Binary block size: {dna_stats['binary_block_size']} bytes")
        print(f"  DNA sequence length: {dna_stats['dna_block_length']} bases per block")
        print(f"  Error correction: {dna_stats['ecc_symbols']} symbols")
        print(f"  Can correct: {dna_stats['correctable_errors']} errors per block")
    
    elif choice == "2":
        img_path = input("Enter image file path: ").strip()
        ecc_symbols = input("Enter ECC symbols (default 10, press Enter): ").strip()
        
        ecc_symbols = int(ecc_symbols) if ecc_symbols else 10
        
        print(f"\nMounting DNA filesystem from {img_path}...")
        fs = DNAFileSystem.open(img_path, ecc_symbols)
        print(f"✓ DNA Filesystem mounted successfully!")
        
        # Show DNA stats
        dna_stats = fs.get_dna_stats()
        print(f"\nDNA Storage Configuration:")
        print(f"  DNA sequence length: {dna_stats['dna_block_length']} bases per block")
        print(f"  Can correct: {dna_stats['correctable_errors']} errors per block")
    
    else:
        print("Invalid choice. Exiting.")
        return
    
    # Interactive command loop
    print("\n" + "=" * 60)
    print("Interactive shell - type 'help' for commands, 'quit' to exit")
    print("=" * 60)
    
    while True:
        try:
            cmd_input = input("\nDNA-FS> ").strip()
            
            if not cmd_input:
                continue
            
            parts = cmd_input.split(maxsplit=2)
            cmd = parts[0]
            
            if cmd == "help":
                print("\nAvailable Commands:")
                print("  ls <path>          - List directory contents")
                print("  tree <path>        - Show directory tree structure")
                print("  mkdir <path>       - Create new directory")
                print("  touch <path>       - Create empty file")
                print("  write <path> <txt> - Write text to file")
                print("  read <path>        - Read and display file content")
                print("  rm <path>          - Delete file or directory")
                print("  info <path>        - Show detailed file information")
                print("  stats              - Show filesystem statistics")
                print("  dna                - Show DNA storage statistics")
                print("  inspect <path>     - Show DNA encoding of a file")
                print("  quit / exit        - Close filesystem and exit")
            
            elif cmd == "ls":
                path = parts[1] if len(parts) > 1 else "/"
                entries = fs.list_directory(path)
                print(f"\nContents of {path}:")
                for entry in entries:
                    print(f"  {entry}")
            
            elif cmd == "tree":
                path = parts[1] if len(parts) > 1 else "/"
                tree_lines = fs.tree(path)
                print()
                for line in tree_lines:
                    print(line)
            
            elif cmd == "mkdir":
                if len(parts) < 2:
                    print("Usage: mkdir <path>")
                    continue
                fs.create_directory(parts[1])
                print(f"✓ Created directory: {parts[1]}")
            
            elif cmd == "touch":
                if len(parts) < 2:
                    print("Usage: touch <path>")
                    continue
                fs.create_file(parts[1])
                print(f"✓ Created file: {parts[1]}")
            
            elif cmd == "write":
                if len(parts) < 3:
                    print("Usage: write <path> <text>")
                    continue
                fs.write_file(parts[1], parts[2].encode('utf-8'))
                print(f"✓ Wrote to file: {parts[1]}")
            
            elif cmd == "read":
                if len(parts) < 2:
                    print("Usage: read <path>")
                    continue
                data = fs.read_file(parts[1])
                text = data.decode('utf-8', errors='replace')
                print(f"\n--- Content of {parts[1]} ---")
                print(text)
                print("--- End ---")
            
            elif cmd == "rm":
                if len(parts) < 2:
                    print("Usage: rm <path>")
                    continue
                fs.delete_file(parts[1])
                print(f"✓ Deleted: {parts[1]}")
            
            elif cmd == "info":
                if len(parts) < 2:
                    print("Usage: info <path>")
                    continue
                info = fs.get_file_info(parts[1])
                if info:
                    type_name = "REGULAR FILE" if info.file_type == FileType.REGULAR else "DIRECTORY"
                    print(f"\nFile Information: {parts[1]}")
                    print(f"  Type: {type_name}")
                    print(f"  Size: {info.size} bytes")
                    print(f"  Blocks: {info.block_count}")
                    print(f"  Created: {time.ctime(info.created)}")
                    print(f"  Modified: {time.ctime(info.modified)}")
                    print(f"  Accessed: {time.ctime(info.accessed)}")
                else:
                    print(f"✗ Path not found: {parts[1]}")
            
            elif cmd == "stats":
                stats = fs.get_stats()
                print("\nFilesystem Statistics:")
                print(f"  Total blocks: {stats.total_blocks}")
                print(f"  Used blocks: {stats.total_blocks - stats.free_blocks}")
                print(f"  Free blocks: {stats.free_blocks}")
                print(f"  Block usage: {((stats.total_blocks - stats.free_blocks) / stats.total_blocks * 100):.1f}%")
                print(f"  Total inodes: {stats.total_inodes}")
                print(f"  Used inodes: {stats.used_inodes}")
                print(f"  Free inodes: {stats.total_inodes - stats.used_inodes}")
                print(f"  Inode usage: {(stats.used_inodes / stats.total_inodes * 100):.1f}%")
            
            elif cmd == "dna":
                dna_stats = fs.get_dna_stats()
                print("\nDNA Storage Statistics:")
                print(f"  Binary block size: {dna_stats['binary_block_size']} bytes")
                print(f"  DNA block length: {dna_stats['dna_block_length']} bases")
                print(f"  Storage overhead: {(dna_stats['dna_block_length'] / (dna_stats['binary_block_size'] * 4) - 1) * 100:.1f}%")
                print(f"  ECC symbols: {dna_stats['ecc_symbols']}")
                print(f"  Correctable errors: {dna_stats['correctable_errors']} per block")
                print(f"  Total blocks: {dna_stats['total_blocks']}")
            
            elif cmd == "inspect":
                if len(parts) < 2:
                    print("Usage: inspect <path>")
                    continue
                
                # Get file info
                _, _, inode_num = fs._lookup_path(parts[1])
                if inode_num is None:
                    print(f"✗ File not found: {parts[1]}")
                    continue
                
                inode = fs.inodes[inode_num]
                if inode.file_type != FileType.REGULAR:
                    print(f"✗ Not a regular file: {parts[1]}")
                    continue
                
                # Read file data
                data = fs.read_file(parts[1])
                
                # Show DNA encoding
                from dna_codec import DNACodec
                codec = DNACodec(fs.device.ecc_symbols)
                dna_sequence = codec.encode(data)
                
                print(f"\nDNA Encoding of {parts[1]}:")
                print(f"  Original size: {len(data)} bytes")
                print(f"  DNA length: {len(dna_sequence)} bases")
                print(f"  First 200 bases: {dna_sequence[:200]}")
                if len(dna_sequence) > 200:
                    print(f"  ... ({len(dna_sequence) - 200} more bases)")
            
            elif cmd in ["quit", "exit"]:
                break
            
            else:
                print(f"✗ Unknown command: {cmd}")
                print("  Type 'help' for available commands")
        
        except KeyboardInterrupt:
            print("\n(Use 'quit' to exit)")
        except Exception as e:
            print(f"✗ Error: {e}")
    
    fs.close()
    print("\n✓ DNA Filesystem closed. Goodbye!")


import time

if __name__ == "__main__":
    shell()