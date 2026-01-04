#!/usr/bin/env python3

def read_bin_file(path):
    with open(path, "rb") as f:
        number = int.from_bytes(f.read(), byteorder='little')
        binary = bin(number)  # Returns '0b11010111...'
        return binary 
