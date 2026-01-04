#!/usr/bin/env python3
"""
DNA Codec - Convert binary data to/from DNA sequences (ACGT)
With Reed-Solomon error correction
"""

from reedsolo import RSCodec

# DNA base mapping
BINARY_TO_DNA = {
    '00': 'A',
    '01': 'C',
    '10': 'G',
    '11': 'T'
}

DNA_TO_BINARY = {
    'A': '00',
    'C': '01',
    'G': '10',
    'T': '11'
}


class DNACodec:
    """Handles conversion between binary data and DNA sequences with error correction"""
    
    def __init__(self, ecc_symbols=10):
        """
        Initialize DNA codec with Reed-Solomon error correction
        
        Args:
            ecc_symbols: Number of error correction symbols (default 10 = ~20% overhead)
                        Can correct up to ecc_symbols/2 errors
        """
        self.ecc_symbols = ecc_symbols
        self.rs = RSCodec(ecc_symbols)
    
    def encode(self, data):
        """
        Encode binary data to DNA sequence with error correction
        
        Args:
            data: bytes object
            
        Returns:
            str: DNA sequence (ACGT string)
        """
        # Step 1: Add Reed-Solomon error correction
        encoded_data = self.rs.encode(data)
        
        # Step 2: Convert to binary string
        binary_str = ''.join(format(byte, '08b') for byte in encoded_data)
        
        # Step 3: Pad to even length (we need pairs for DNA encoding)
        if len(binary_str) % 2 != 0:
            binary_str += '0'
        
        # Step 4: Convert binary pairs to DNA bases
        dna_sequence = ''
        for i in range(0, len(binary_str), 2):
            pair = binary_str[i:i+2]
            dna_sequence += BINARY_TO_DNA[pair]
        
        return dna_sequence
    
    def decode(self, dna_sequence):
        """
        Decode DNA sequence back to binary data with error correction
        
        Args:
            dna_sequence: str (ACGT sequence)
            
        Returns:
            bytes: Original data (with errors corrected if possible)
        """
        # Step 1: Convert DNA bases to binary string
        binary_str = ''
        for base in dna_sequence:
            if base in DNA_TO_BINARY:
                binary_str += DNA_TO_BINARY[base]
            else:
                # Handle invalid bases (treat as mutation)
                binary_str += '00'  # Default to A
        
        # Step 2: Convert binary string to bytes
        byte_list = []
        for i in range(0, len(binary_str), 8):
            byte_chunk = binary_str[i:i+8]
            if len(byte_chunk) == 8:
                byte_list.append(int(byte_chunk, 2))
        
        encoded_data = bytes(byte_list)
        
        # Step 3: Apply Reed-Solomon error correction
        try:
            decoded_data = self.rs.decode(encoded_data)
            # Handle both bytearray and tuple returns
            if isinstance(decoded_data, (tuple, list)):
                decoded_data = decoded_data[0]
            return bytes(decoded_data)
        except Exception as e:
            # If too many errors to correct, return corrupted data
            # Silently handle common case of decoding empty/zero data
            if "cannot be interpreted as an integer" not in str(e):
                print(f"Warning: DNA sequence has too many errors to correct: {e}")
            return encoded_data[:len(encoded_data)-self.ecc_symbols]
    
    def get_overhead(self):
        """Return the error correction overhead percentage"""
        return (self.ecc_symbols / 255) * 100
    
    def can_correct_errors(self):
        """Return maximum number of correctable errors"""
        return self.ecc_symbols // 2


def bytes_to_dna(data, ecc_symbols=10):
    """Convenience function: Convert bytes to DNA sequence"""
    codec = DNACodec(ecc_symbols)
    return codec.encode(data)


def dna_to_bytes(dna_sequence, ecc_symbols=10):
    """Convenience function: Convert DNA sequence to bytes"""
    codec = DNACodec(ecc_symbols)
    return codec.decode(dna_sequence)


# Example usage and testing
if __name__ == "__main__":
    # Test basic encoding/decoding
    codec = DNACodec(ecc_symbols=10)
    
    # Test data
    original = b"Hello, DNA World!"
    print(f"Original data: {original}")
    print(f"Original size: {len(original)} bytes")
    
    # Encode to DNA
    dna = codec.encode(original)
    print(f"\nDNA sequence: {dna}")
    print(f"DNA length: {len(dna)} bases")
    print(f"Overhead: {codec.get_overhead():.1f}%")
    print(f"Can correct up to {codec.can_correct_errors()} errors")
    
    # Decode back
    decoded = codec.decode(dna)
    print(f"\nDecoded data: {decoded}")
    print(f"Match: {original == decoded}")
    
    # Test error correction
    print("\n--- Testing Error Correction ---")
    # Introduce some mutations
    dna_list = list(dna)
    mutation_positions = [5, 15, 25]
    
    for pos in mutation_positions:
        if pos < len(dna_list):
            old_base = dna_list[pos]
            # Mutate to different base
            mutations = {'A': 'T', 'C': 'G', 'G': 'A', 'T': 'C'}
            dna_list[pos] = mutations.get(old_base, 'A')
            print(f"Mutation at position {pos}: {old_base} → {dna_list[pos]}")
    
    mutated_dna = ''.join(dna_list)
    
    # Try to decode mutated DNA
    recovered = codec.decode(mutated_dna)
    print(f"\nRecovered data: {recovered}")
    print(f"Recovery successful: {original == recovered}")