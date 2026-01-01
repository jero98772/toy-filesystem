#!/usr/bin/env python3
"""
Test script for the toy filesystem implementation
"""

from pathlib import Path
from toy_filesystem import ToyFileSystem
import os


def test_filesystem():
    """Run comprehensive tests on the filesystem"""
    img_path = Path("test_filesystem.img")
    
    # Clean up any existing test file
    if img_path.exists():
        os.remove(img_path)
    
    print("Creating filesystem (10MB)...")
    fs = ToyFileSystem.create(img_path, 10)
    
    print("\n1. Creating directories...")
    fs.create_directory("/home")
    fs.create_directory("/home/user")
    fs.create_directory("/home/user/documents")
    print("   Created: /home, /home/user, /home/user/documents")
    
    print("\n2. Creating and writing files...")
    fs.create_file("/home/user/hello.txt")
    fs.write_file("/home/user/hello.txt", b"Hello, File System!")
    print("   Created: /home/user/hello.txt")
    
    fs.create_file("/home/user/data.bin")
    test_data = bytes([1, 2, 3, 4, 5, 42, 100, 255])
    fs.write_file("/home/user/data.bin", test_data)
    print("   Created: /home/user/data.bin")
    
    fs.create_file("/home/user/documents/readme.txt")
    readme_content = b"This is a README file\nLine 2\nLine 3"
    fs.write_file("/home/user/documents/readme.txt", readme_content)
    print("   Created: /home/user/documents/readme.txt")
    
    print("\n3. Reading files...")
    content = fs.read_file("/home/user/hello.txt")
    print(f"   /home/user/hello.txt: {content.decode('utf-8')}")
    assert content == b"Hello, File System!"
    
    data = fs.read_file("/home/user/data.bin")
    print(f"   /home/user/data.bin: {list(data)}")
    assert data == test_data
    
    readme = fs.read_file("/home/user/documents/readme.txt")
    print(f"   /home/user/documents/readme.txt:\n   {readme.decode('utf-8').replace(chr(10), chr(10) + '   ')}")
    assert readme == readme_content
    
    print("\n4. Listing directories...")
    root_files = fs.list_directory("/")
    print(f"   Root directory: {root_files}")
    
    home_files = fs.list_directory("/home")
    print(f"   /home: {home_files}")
    
    user_files = fs.list_directory("/home/user")
    print(f"   /home/user: {user_files}")
    
    doc_files = fs.list_directory("/home/user/documents")
    print(f"   /home/user/documents: {doc_files}")
    
    print("\n5. Getting file information...")
    info = fs.get_file_info("/home/user/hello.txt")
    print(f"   File: /home/user/hello.txt")
    print(f"   Type: {info.file_type.name}")
    print(f"   Size: {info.size} bytes")
    print(f"   Created: {info.created}")
    print(f"   Modified: {info.modified}")
    
    print("\n6. Getting filesystem statistics...")
    stats = fs.get_stats()
    print(f"   Total blocks: {stats.total_blocks}")
    print(f"   Free blocks: {stats.free_blocks}")
    print(f"   Used blocks: {stats.total_blocks - stats.free_blocks}")
    print(f"   Total inodes: {stats.total_inodes}")
    print(f"   Used inodes: {stats.used_inodes}")
    print(f"   Free inodes: {stats.total_inodes - stats.used_inodes}")
    
    print("\n7. Testing persistence (closing and reopening)...")
    fs.close()
    
    fs2 = ToyFileSystem.open(img_path)
    content2 = fs2.read_file("/home/user/hello.txt")
    print(f"   Re-read content: {content2.decode('utf-8')}")
    assert content2 == b"Hello, File System!"
    
    user_files2 = fs2.list_directory("/home/user")
    print(f"   Re-read directory: {user_files2}")
    
    print("\n8. Testing file deletion...")
    fs2.delete_file("/home/user/data.bin")
    print("   Deleted: /home/user/data.bin")
    
    user_files3 = fs2.list_directory("/home/user")
    print(f"   Directory after deletion: {user_files3}")
    assert "data.bin" not in user_files3
    
    print("\n9. Writing larger file (multiple blocks)...")
    large_content = b"X" * 10000  # ~10KB, needs 3 blocks
    fs2.create_file("/home/user/large.txt")
    fs2.write_file("/home/user/large.txt", large_content)
    print(f"   Created large file: {len(large_content)} bytes")
    
    read_large = fs2.read_file("/home/user/large.txt")
    print(f"   Read large file: {len(read_large)} bytes")
    assert read_large == large_content
    
    print("\n10. Final statistics...")
    final_stats = fs2.get_stats()
    print(f"   Total blocks: {final_stats.total_blocks}")
    print(f"   Free blocks: {final_stats.free_blocks}")
    print(f"   Used blocks: {final_stats.total_blocks - final_stats.free_blocks}")
    print(f"   Used inodes: {final_stats.used_inodes}")
    
    fs2.close()
    
    print("\n✅ All tests passed!")
    print(f"\nFilesystem image saved as: {img_path}")
    print("You can interact with it using:")
    print(f"  python toy_filesystem.py mount {img_path}")
    
    # Clean up (optional - comment out to keep the image)
    # os.remove(img_path)


if __name__ == "__main__":
    test_filesystem()