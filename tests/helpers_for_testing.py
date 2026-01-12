# =============================================================================
# Shared helper functions to create test STL data
# =============================================================================

GSI_SIZE = 1024
TTI_SIZE = 128

# Teletext sync pattern: clock run-in (0x55 0x55) + framing code (0x27)
TELETEXT_SYNC = bytes([0x55, 0x55, 0x27])


def make_gsi_block(
    dfc: bytes = b"STL25.01",
    cct: bytes = b"00",
    title: bytes = b"Test Title",
    language_code: bytes = b"09",  # English
    programme_name: bytes = b"",
) -> bytes:
    """Create a 1024-byte GSI block with specified fields."""
    gsi = bytearray(GSI_SIZE)

    # Code Page Number (bytes 0-2)
    gsi[0:3] = b"850"

    # Disk Format Code (bytes 3-10, 8 bytes)
    gsi[3:11] = dfc.ljust(8)[:8]

    # Character Code Table (bytes 12-13)
    gsi[12:14] = cct.ljust(2)[:2]

    # Language Code (bytes 14-15)
    gsi[14:16] = language_code.ljust(2)[:2]

    # Title (bytes 16-47)
    gsi[16:48] = title.ljust(32)[:32]

    # Programme Name (bytes 48-79)
    gsi[48:80] = programme_name.ljust(32)[:32]

    return bytes(gsi)


def make_tti_block(
    sn: int = 1,
    cs: int = 0x00,  # Single block
    tci: tuple = (0, 0, 1, 0),  # 00:00:01:00
    tco: tuple = (0, 0, 3, 0),  # 00:00:03:00
    text: bytes = b"Hello World",
    vp: int = 20,
    jc: int = 0x02,  # Centered
) -> bytes:
    """Create a 128-byte TTI block with specified fields."""
    tti = bytearray(TTI_SIZE)

    # Subtitle Group Number (byte 0)
    tti[0] = 0

    # Subtitle Number (bytes 1-2, big-endian)
    tti[1] = (sn >> 8) & 0xFF
    tti[2] = sn & 0xFF

    # Extension Block Number (byte 3)
    tti[3] = 0xFF  # Standard block

    # Cumulative Status (byte 4)
    tti[4] = cs

    # Time Code In (bytes 5-8)
    tti[5:9] = bytes(tci)

    # Time Code Out (bytes 9-12)
    tti[9:13] = bytes(tco)

    # Vertical Position (byte 13)
    tti[13] = vp

    # Justification Code (byte 14)
    tti[14] = jc

    # Comment Flag (byte 15)
    tti[15] = 0  # Subtitle, not comment

    # Text field (bytes 16-127, 112 bytes)
    # Pad with unused space marker (0x8F)
    text_field = text.ljust(112, b"\x8f")[:112]
    tti[16:128] = text_field

    return bytes(tti)


def make_stl_file(gsi: bytes = None, tti_blocks: list = None) -> bytes:
    """Create a complete STL file with GSI header and TTI blocks."""
    if gsi is None:
        gsi = make_gsi_block()
    if tti_blocks is None:
        tti_blocks = [make_tti_block()]

    return gsi + b"".join(tti_blocks)
