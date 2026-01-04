#!/usr/bin/env python3
"""
Interactive shell for the File System
"""

from tools.filesystem import FileSystem, FileType


def shell():
    """Interactive filesystem shell"""
    print("File System Shell")
    print("=" * 50)
    
    # Get filesystem path and action
    print("\nWhat would you like to do?")
    print("1. Create new filesystem")
    print("2. Mount existing filesystem")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "1":
        img_path = input("Enter image file path: ").strip()
        size_mb = input("Enter size in MB: ").strip()
        
        size_mb = int(size_mb)
        
        print(f"\nCreating filesystem at {img_path} with size {size_mb}MB...")
        fs = FileSystem.create(img_path, size_mb)
        print(f"Filesystem created successfully!")
    
    elif choice == "2":
        img_path = input("Enter image file path: ").strip()
        
        print(f"\nMounting filesystem from {img_path}...")
        fs = FileSystem.open(img_path)
        print(f"Filesystem mounted successfully!")
    
    else:
        print("Invalid choice. Exiting.")
        return
    
    # Interactive command loop
    print("\nInteractive shell - type 'help' for commands, 'quit' to exit")
    
    while True:
        cmd_input = input("> ").strip()
        
        if not cmd_input:
            continue
        
        parts = cmd_input.split(maxsplit=2)
        cmd = parts[0]
        
        if cmd == "help":
            print("Commands:")
            print("  ls <path>        - List directory")
            print("  tree <path>      - Show directory tree")
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
        
        elif cmd == "tree":
            path = parts[1] if len(parts) > 1 else "/"
            tree_lines = fs.tree(path)
            for line in tree_lines:
                print(line)
        
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
            text = data.decode('utf-8', errors='replace')
            print(text)
        
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
            if info:
                type_name = "REGULAR" if info.file_type == FileType.REGULAR else "DIRECTORY"
                print(f"Type: {type_name}")
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
    
    fs.close()
    print("\nFilesystem closed. Goodbye!")

def create_filesystem(img_path, size_mb):
    """Create a new filesystem and return success status"""
    fs = FileSystem.create(img_path, size_mb)
    fs.close()
    return {"status": "success", "message": f"Filesystem created at {img_path}"}


def open_filesystem(img_path):
    """Open an existing filesystem"""
    fs = FileSystem.open(img_path)
    return fs


def execute_command(fs, command, args=None):
    """Execute a command on the filesystem and return result as dict"""
    if args is None:
        args = []
    
    if command == "help":
        return {
            "commands": {
                "ls": "List directory",
                "tree": "Show directory tree",
                "mkdir": "Create directory",
                "touch": "Create empty file",
                "write": "Write text to file",
                "read": "Read file content",
                "rm": "Delete file",
                "info": "Show file info",
                "stats": "Show filesystem statistics"
            }
        }
    
    elif command == "ls":
        path = args[0] if len(args) > 0 else "/"
        entries = fs.list_directory(path)
        return {"path": path, "entries": entries}
    
    elif command == "tree":
        path = args[0] if len(args) > 0 else "/"
        tree_lines = fs.tree(path)
        return {"path": path, "tree": tree_lines}
    
    elif command == "mkdir":
        if len(args) < 1:
            return {"error": "Usage: mkdir <path>"}
        fs.create_directory(args[0])
        return {"status": "success", "message": f"Created directory: {args[0]}"}
    
    elif command == "touch":
        if len(args) < 1:
            return {"error": "Usage: touch <path>"}
        fs.create_file(args[0])
        return {"status": "success", "message": f"Created file: {args[0]}"}
    
    elif command == "write":
        if len(args) < 2:
            return {"error": "Usage: write <path> <text>"}
        fs.write_file(args[0], args[1].encode('utf-8'))
        return {"status": "success", "message": f"Wrote to file: {args[0]}"}
    
    elif command == "read":
        if len(args) < 1:
            return {"error": "Usage: read <path>"}
        data = fs.read_file(args[0])
        text = data.decode('utf-8', errors='replace')
        return {"path": args[0], "content": text}
    
    elif command == "rm":
        if len(args) < 1:
            return {"error": "Usage: rm <path>"}
        fs.delete_file(args[0])
        return {"status": "success", "message": f"Deleted: {args[0]}"}
    
    elif command == "info":
        if len(args) < 1:
            return {"error": "Usage: info <path>"}
        info = fs.get_file_info(args[0])
        if info:
            type_name = "REGULAR" if info.file_type == FileType.REGULAR else "DIRECTORY"
            return {
                "path": args[0],
                "type": type_name,
                "size": info.size,
                "created": info.created,
                "modified": info.modified,
                "accessed": info.accessed
            }
        return {"error": f"File not found: {args[0]}"}
    
    elif command == "stats":
        stats = fs.get_stats()
        return {
            "total_blocks": stats.total_blocks,
            "free_blocks": stats.free_blocks,
            "used_blocks": stats.total_blocks - stats.free_blocks,
            "total_inodes": stats.total_inodes,
            "used_inodes": stats.used_inodes,
            "free_inodes": stats.total_inodes - stats.used_inodes
        }
    
    else:
        return {"error": f"Unknown command: {command}"}

#if __name__ == "__main__":
#    shell()