#!/usr/bin/env python3
"""
Script to demonstrate interactive shell functionality
"""

import subprocess
import sys

# Commands to run
commands = """ls /
mkdir /projects
touch /projects/notes.txt
write /projects/notes.txt This is a test note
read /projects/notes.txt
ls /projects
info /projects/notes.txt
stats
quit
"""

print("Demonstrating interactive filesystem shell...")
print("=" * 60)

# Run the commands
process = subprocess.Popen(
    [sys.executable, 'toy_filesystem.py', 'mount', 'test_filesystem.img'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

stdout, stderr = process.communicate(input=commands)

print(stdout)
if stderr:
    print("Errors:", stderr, file=sys.stderr)

print("=" * 60)
print("Interactive shell test complete!")