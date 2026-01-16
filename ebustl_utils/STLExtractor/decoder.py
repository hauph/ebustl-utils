"""
Teletext decoder for EBU STL extraction.

This is a minimal implementation of teletext packet decoding. Only the
functionality needed for subtitle extraction (packets 0-25) is included.

Subtitle pages always use standard text coding (coding 0), so we don't need
to track magazine coding states like a full teletext decoder would.

References:
    - ETSI EN 300 706 V1.2.1 - Enhanced Teletext specification
"""

from typing import List, Tuple, Union

# Teletext G0 character mapping for pound sign.
# In teletext, byte position 0x23 displays as £ (pound sign) instead of # (hash).
# Other characters remain as standard ASCII.
TELETEXT_CHAR_MAP = {
    0x23: "£",  # Pound sign (ASCII position has #)
}


def teletext_byte_to_char(byte: int) -> str:
    """
    Convert a teletext byte to the correct Unicode character.

    Applies teletext character mapping where byte 0x23 displays as £ (pound sign).
    All other characters use standard ASCII interpretation.
    """
    if byte in TELETEXT_CHAR_MAP:
        return TELETEXT_CHAR_MAP[byte]
    return chr(byte)


# Pre-computed Hamming 8/4 lookup table.
# Index: input byte (0-255)
# Value: (decoded_nibble, error_count)
#   - decoded_nibble: 4-bit decoded value (0-15)
#   - error_count: 0=no error, 1=corrected single-bit error, 2=uncorrectable
#
# Data bits are at positions 1, 3, 5, 7. Parity/check bits at 0, 2, 4, 6.
HAMMING_8_4_TABLE: Tuple[Tuple[int, int], ...] = (
    (1, 1),
    (0, 2),
    (1, 0),
    (1, 1),
    (0, 2),
    (0, 1),
    (1, 1),
    (1, 2),
    (2, 2),
    (2, 1),
    (1, 1),
    (3, 2),
    (10, 1),
    (2, 2),
    (3, 2),
    (7, 1),
    (0, 2),
    (0, 1),
    (1, 1),
    (1, 2),
    (0, 1),
    (0, 0),
    (1, 2),
    (0, 1),
    (6, 1),
    (2, 2),
    (3, 2),
    (11, 1),
    (2, 2),
    (0, 1),
    (3, 1),
    (3, 2),
    (4, 2),
    (12, 1),
    (1, 1),
    (5, 2),
    (4, 1),
    (4, 2),
    (5, 2),
    (7, 1),
    (6, 1),
    (6, 2),
    (7, 2),
    (7, 1),
    (6, 2),
    (7, 1),
    (7, 1),
    (7, 0),
    (6, 1),
    (4, 2),
    (5, 2),
    (5, 1),
    (4, 2),
    (0, 1),
    (13, 1),
    (5, 2),
    (6, 0),
    (6, 1),
    (6, 1),
    (7, 2),
    (6, 1),
    (6, 2),
    (7, 2),
    (7, 1),
    (0, 2),
    (2, 1),
    (1, 1),
    (1, 2),
    (4, 1),
    (0, 2),
    (1, 2),
    (9, 1),
    (2, 1),
    (2, 0),
    (3, 2),
    (2, 1),
    (2, 2),
    (2, 1),
    (3, 1),
    (3, 2),
    (8, 1),
    (0, 2),
    (1, 2),
    (5, 1),
    (0, 2),
    (0, 1),
    (3, 1),
    (1, 2),
    (2, 2),
    (2, 1),
    (3, 1),
    (3, 2),
    (3, 1),
    (2, 2),
    (3, 0),
    (3, 1),
    (4, 1),
    (4, 2),
    (5, 2),
    (5, 1),
    (4, 0),
    (4, 1),
    (4, 1),
    (5, 2),
    (6, 2),
    (2, 1),
    (15, 1),
    (7, 2),
    (4, 1),
    (6, 2),
    (7, 2),
    (7, 1),
    (4, 2),
    (5, 1),
    (5, 1),
    (5, 0),
    (4, 1),
    (4, 2),
    (5, 2),
    (5, 1),
    (6, 1),
    (6, 2),
    (7, 2),
    (5, 1),
    (6, 2),
    (14, 1),
    (3, 1),
    (7, 2),
    (8, 2),
    (12, 1),
    (1, 1),
    (9, 2),
    (10, 1),
    (8, 2),
    (9, 2),
    (9, 1),
    (10, 1),
    (10, 2),
    (11, 2),
    (11, 1),
    (10, 0),
    (10, 1),
    (10, 1),
    (11, 2),
    (8, 1),
    (8, 2),
    (9, 2),
    (11, 1),
    (8, 2),
    (0, 1),
    (13, 1),
    (9, 2),
    (10, 2),
    (11, 1),
    (11, 1),
    (11, 0),
    (10, 1),
    (10, 2),
    (11, 2),
    (11, 1),
    (12, 1),
    (12, 0),
    (13, 2),
    (12, 1),
    (12, 2),
    (12, 1),
    (13, 1),
    (13, 2),
    (14, 2),
    (12, 1),
    (15, 1),
    (15, 2),
    (10, 1),
    (14, 2),
    (15, 2),
    (7, 1),
    (12, 2),
    (12, 1),
    (13, 1),
    (13, 2),
    (13, 1),
    (12, 2),
    (13, 0),
    (13, 1),
    (6, 1),
    (14, 2),
    (15, 2),
    (11, 1),
    (14, 2),
    (14, 1),
    (13, 1),
    (15, 2),
    (8, 1),
    (8, 2),
    (9, 2),
    (9, 1),
    (8, 2),
    (9, 1),
    (9, 1),
    (9, 0),
    (10, 2),
    (2, 1),
    (15, 1),
    (11, 2),
    (10, 1),
    (10, 2),
    (11, 2),
    (9, 1),
    (8, 0),
    (8, 1),
    (8, 1),
    (9, 2),
    (8, 1),
    (8, 2),
    (9, 2),
    (9, 1),
    (8, 1),
    (10, 2),
    (11, 2),
    (11, 1),
    (10, 2),
    (14, 1),
    (3, 1),
    (11, 2),
    (12, 2),
    (12, 1),
    (15, 1),
    (13, 2),
    (4, 1),
    (12, 2),
    (13, 2),
    (9, 1),
    (15, 1),
    (14, 2),
    (15, 0),
    (15, 1),
    (14, 2),
    (14, 1),
    (15, 1),
    (15, 2),
    (8, 1),
    (12, 2),
    (13, 2),
    (5, 1),
    (12, 2),
    (14, 1),
    (13, 1),
    (13, 2),
    (14, 2),
    (14, 1),
    (15, 1),
    (15, 2),
    (14, 1),
    (14, 0),
    (15, 2),
    (14, 1),
)


def hamming_8_4_decode(byte: int) -> Tuple[int, int]:
    """
    Decode a Hamming 8/4 encoded byte using lookup table.

    Hamming 8/4 encodes 4 data bits into 8 bits with error correction.
    Data bits are at positions 1, 3, 5, 7.

    Args:
        byte: The encoded byte (0-255)

    Returns:
        Tuple of (decoded_nibble, error_count)
        - decoded_nibble: 4-bit decoded value (0-15)
        - error_count: 0=no error, 1=corrected, 2=uncorrectable
    """
    return HAMMING_8_4_TABLE[byte & 0xFF]


def decode_teletext_line(data: bytes) -> List[Union[int, str, Tuple[int, int]]]:
    """
    Decode a 42-byte teletext packet for subtitle extraction.

    The packet structure is:
    - Byte 0-1: Hamming 8/4 encoded magazine (3 bits) and packet number (5 bits)
    - Bytes 2-41: Data (text characters with parity bits)

    For packet 0 (page header):
        Returns: [magazine, packet, page, subpage, control, header_text]

    For packets 1-25 (page rows):
        Returns: [magazine, packet, text]

    Args:
        data: 42-byte teletext packet

    Returns:
        List containing decoded packet data.
    """
    decoded_data: List[Union[int, str, Tuple[int, int]]] = []
    control = 0

    # Decode magazine and packet number from first two bytes
    decode = hamming_8_4_decode(data[0])[0]
    magazine = decode & 0x7
    if magazine == 0:
        magazine = 8
    packet = decode >> 3

    decode = hamming_8_4_decode(data[1])[0]
    packet |= decode << 1

    decoded_data.append(magazine)
    decoded_data.append(packet)

    if packet == 0:
        # Page header packet
        # Returns: [magazine, packet, page, subpage, control, header_text]
        page = (hamming_8_4_decode(data[3])[0] << 4) | hamming_8_4_decode(data[2])[0]
        decoded_data.append(page)

        subpage = hamming_8_4_decode(data[4])[0]

        decode = hamming_8_4_decode(data[5])[0]
        subpage |= (decode & 0x7) << 4
        control |= (decode & 0x8) << 1

        subpage |= hamming_8_4_decode(data[6])[0] << 8

        decode = hamming_8_4_decode(data[7])[0]
        subpage |= (decode & 0x3) << 12
        decoded_data.append(subpage)

        control |= (decode & 0xC) << 3

        decode = hamming_8_4_decode(data[8])[0]
        control |= decode << 7

        decode = hamming_8_4_decode(data[9])[0]
        control |= decode << 11

        decoded_data.append(control)

        # Decode header text (bytes 10-41)
        header = ""
        for i in range(10, 42):
            char_byte = data[i] & 0x7F  # Strip parity bit
            if char_byte < 0x20:
                # Control code - represent as hex in brackets
                header += f"⟦{char_byte:02X}⟧"
            else:
                header += teletext_byte_to_char(char_byte)

        decoded_data.append(header)

    elif packet < 26:
        # Page row packets (1-25)
        # Apply teletext character mapping (0x23 → £)
        text = ""
        for i in range(2, 42):
            char_byte = data[i] & 0x7F  # Strip parity bit
            if char_byte < 0x20:
                # Control code
                text += f"⟦{char_byte:02X}⟧"
            else:
                text += teletext_byte_to_char(char_byte)
        decoded_data.append(text)

    # Packets 26-31 are not needed for subtitle extraction
    # (enhancement data, links, broadcast service data)

    return decoded_data
