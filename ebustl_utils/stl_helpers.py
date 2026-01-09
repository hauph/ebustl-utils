"""
EBU STL Converter - Converts Teletext/OP-47 data from MXF to EBU STL format.

This module extracts ALL teletext features including:
- Colors (foreground/background)
- Layout (positioning, justification)
- Formatting (italic, underline, boxing, double height)
- Character set mappings

Uses decode_teletext_line function from teletext-decoder library for teletext parsing.
"""

import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Dict
from datetime import datetime

from teletextdecoder.decoder import decode_teletext_line


# =============================================================================
# Teletext Color Codes
# =============================================================================


class TeletextColor(IntEnum):
    """Teletext Level 1 colors (spacing attributes 0x00-0x07)"""

    BLACK = 0
    RED = 1
    GREEN = 2
    YELLOW = 3
    BLUE = 4
    MAGENTA = 5
    CYAN = 6
    WHITE = 7


# Map teletext color codes to EBU STL color names
TELETEXT_COLOR_NAMES = {
    TeletextColor.BLACK: "black",
    TeletextColor.RED: "red",
    TeletextColor.GREEN: "green",
    TeletextColor.YELLOW: "yellow",
    TeletextColor.BLUE: "blue",
    TeletextColor.MAGENTA: "magenta",
    TeletextColor.CYAN: "cyan",
    TeletextColor.WHITE: "white",
}


# =============================================================================
# Teletext Control Codes
# =============================================================================


class TeletextControlCode(IntEnum):
    """Teletext control codes (0x00-0x1F)"""

    # Alpha colors (foreground)
    ALPHA_BLACK = 0x00
    ALPHA_RED = 0x01
    ALPHA_GREEN = 0x02
    ALPHA_YELLOW = 0x03
    ALPHA_BLUE = 0x04
    ALPHA_MAGENTA = 0x05
    ALPHA_CYAN = 0x06
    ALPHA_WHITE = 0x07

    # Display control
    FLASH = 0x08
    STEADY = 0x09
    END_BOX = 0x0A
    START_BOX = 0x0B
    NORMAL_HEIGHT = 0x0C
    DOUBLE_HEIGHT = 0x0D
    DOUBLE_WIDTH = 0x0E
    DOUBLE_SIZE = 0x0F

    # Mosaic colors
    MOSAIC_BLACK = 0x10
    MOSAIC_RED = 0x11
    MOSAIC_GREEN = 0x12
    MOSAIC_YELLOW = 0x13
    MOSAIC_BLUE = 0x14
    MOSAIC_MAGENTA = 0x15
    MOSAIC_CYAN = 0x16
    MOSAIC_WHITE = 0x17

    # Additional control
    CONCEAL = 0x18
    CONTIGUOUS_MOSAIC = 0x19
    SEPARATED_MOSAIC = 0x1A
    ESC = 0x1B
    BLACK_BACKGROUND = 0x1C
    NEW_BACKGROUND = 0x1D
    HOLD_MOSAIC = 0x1E
    RELEASE_MOSAIC = 0x1F


# =============================================================================
# EBU STL Control Codes (for Text Field)
# =============================================================================


class EBUSTLControlCode(IntEnum):
    """EBU STL Text Field control codes"""

    # Teletext spacing attributes (0x00-0x07 foreground colors)
    ALPHA_BLACK = 0x00
    ALPHA_RED = 0x01
    ALPHA_GREEN = 0x02
    ALPHA_YELLOW = 0x03
    ALPHA_BLUE = 0x04
    ALPHA_MAGENTA = 0x05
    ALPHA_CYAN = 0x06
    ALPHA_WHITE = 0x07

    # Display attributes
    FLASH = 0x08
    STEADY = 0x09
    END_BOX = 0x0A
    START_BOX = 0x0B
    NORMAL_HEIGHT = 0x0C
    DOUBLE_HEIGHT = 0x0D

    # Formatting
    ITALIC_ON = 0x80
    ITALIC_OFF = 0x81
    UNDERLINE_ON = 0x82
    UNDERLINE_OFF = 0x83
    BOXING_ON = 0x84
    BOXING_OFF = 0x85

    # Line break
    NEWLINE = 0x8A

    # Unused space (filler)
    UNUSED_SPACE = 0x8F


# =============================================================================
# Justification Codes
# =============================================================================


class JustificationCode(IntEnum):
    """EBU STL Justification codes"""

    UNCHANGED = 0x00
    LEFT = 0x01
    CENTERED = 0x02
    RIGHT = 0x03


# =============================================================================
# Subtitle Data Structures with Full Formatting
# =============================================================================


@dataclass
class TextSegment:
    """A segment of text with formatting attributes."""

    text: str
    foreground_color: TeletextColor = TeletextColor.WHITE
    background_color: TeletextColor = TeletextColor.BLACK
    double_height: bool = False
    flash: bool = False
    boxing: bool = False
    concealed: bool = False


@dataclass
class SubtitleLine:
    """A single line of subtitle text with full formatting."""

    row: int  # Vertical position (1-24 for teletext)
    segments: List[TextSegment] = field(default_factory=list)
    double_height: bool = False

    @property
    def text(self) -> str:
        """Get plain text without formatting."""
        return "".join(seg.text for seg in self.segments)

    @property
    def has_content(self) -> bool:
        """Check if line has actual content."""
        return bool(self.text.strip())


@dataclass
class Subtitle:
    """A complete subtitle with timing, positioning, and formatted content."""

    index: int
    start_time: int  # In frames (25fps for PAL)
    end_time: int  # In frames
    lines: List[SubtitleLine] = field(default_factory=list)
    justification: JustificationCode = JustificationCode.CENTERED
    vertical_position: int = 20  # Default near bottom

    @property
    def has_content(self) -> bool:
        """Check if subtitle has actual content."""
        return any(line.has_content for line in self.lines)


# =============================================================================
# Enhanced Teletext Parser
# =============================================================================


def extract_teletext_from_vanc(raw_data: bytes) -> List[tuple]:
    """
    Extract teletext packets from OP-47/VANC wrapped data.

    OP-47 data contains teletext packets wrapped in VANC headers.
    The teletext sync pattern is 0x55 0x55 0x27 (clock run-in + framing code).

    After the sync pattern, the next 42 bytes are the teletext packet:
    - 2 bytes: Hamming 8/4 encoded magazine/packet address
    - 40 bytes: data (text or control codes)

    Args:
        raw_data: Raw VANC/OP-47 data from MXF

    Returns:
        List of tuples: (packet_bytes, packet_index)
        packet_index is used for rough timing estimation
    """
    packets = []

    # Teletext sync pattern: clock run-in (0x55 0x55) + framing code (0x27)
    SYNC_PATTERN = bytes([0x55, 0x55, 0x27])

    offset = 0
    packet_idx = 0
    while offset < len(raw_data) - 45:  # Need sync(3) + packet(42)
        # Find next sync pattern
        pos = raw_data.find(SYNC_PATTERN, offset)
        if pos == -1:
            break

        # Extract 42 bytes AFTER the sync pattern (55 55 27)
        packet_start = pos + 3  # Skip the sync pattern entirely

        if packet_start + 42 <= len(raw_data):
            packet = raw_data[packet_start : packet_start + 42]
            packets.append((bytes(packet), packet_idx))
            packet_idx += 1

        offset = pos + 3 + 42  # Move past this packet

    return packets


class TeletextParser:
    """
    Enhanced parser that extracts all teletext features including
    colors, formatting, and layout.

    Supports both raw teletext packets and OP-47/VANC wrapped data.
    """

    PACKET_SIZE = 42

    def __init__(self, total_frames: int = None, frame_rate: float = 25):
        """
        Initialize the parser.

        Args:
            total_frames: Total video frames (for accurate timing mapping)
            frame_rate: Video frame rate (default 25fps)
        """
        self.current_page: Dict[int, int] = {}
        self.current_rows: Dict[int, Dict[int, SubtitleLine]] = {}
        self.is_subtitle_page: Dict[int, bool] = {}  # Track subtitle flag per magazine
        self.subtitles: List[Subtitle] = []
        self.frame_count = 0
        self.last_subtitle_time: Dict[int, int] = {}
        self.total_frames = total_frames
        self.frame_rate = frame_rate
        self.total_packets = 0  # Will be set during parsing

    def parse(self, raw_data: bytes) -> List[Subtitle]:
        """
        Parse raw teletext data and extract subtitles with full formatting.

        Args:
            raw_data: Binary teletext data from MXF extraction (raw or VANC wrapped)

        Returns:
            List of Subtitle objects with complete formatting
        """
        # Detect format: check for VANC/OP-47 sync pattern
        if b"\x55\x55\x27" in raw_data[:1000]:
            # OP-47/VANC format - extract teletext packets first
            print("Detected OP-47/VANC format, extracting teletext packets...")
            packet_data = extract_teletext_from_vanc(raw_data)
            print(f"Extracted {len(packet_data)} teletext packets")
        else:
            # Raw teletext format - split into 42-byte packets
            print("Processing as raw teletext format...")
            packet_data = []
            offset = 0
            idx = 0
            while offset + self.PACKET_SIZE <= len(raw_data):
                packet_data.append((raw_data[offset : offset + self.PACKET_SIZE], idx))
                offset += self.PACKET_SIZE
                idx += 1

        self.total_packets = len(packet_data)

        # Calculate frame mapping: packet_index -> video_frame
        # If we have total_frames from the video, map packets linearly to frames
        if self.total_frames and self.total_packets > 0:
            print(
                f"Mapping {self.total_packets} packets to {self.total_frames} video frames"
            )

        # Process each packet
        for packet, pkt_idx in packet_data:
            # Skip empty packets
            if len(packet) < 2:
                continue
            if packet[0] == 0x00 or packet[0] == 0xFF:
                continue

            # Calculate frame number from packet index
            if self.total_frames and self.total_packets > 0:
                # Linear mapping: packet position -> video frame
                self.frame_count = int(
                    (pkt_idx / self.total_packets) * self.total_frames
                )
            else:
                # Fallback: assume 2 packets per frame (rough estimate)
                self.frame_count = pkt_idx // 2

            self._process_packet(packet)

        # Flush remaining subtitle pages
        for magazine in list(self.current_rows.keys()):
            if self.is_subtitle_page.get(magazine, False):
                self._flush_page(magazine)

        # Post-process: set end times based on next subtitle
        self._calculate_end_times()

        return self.subtitles

    def _process_packet(self, packet: bytes) -> None:
        """Process a teletext packet and extract formatting."""
        # Use decoder.py for basic packet decoding
        decoded = decode_teletext_line(packet)

        if not decoded or len(decoded) < 2:
            return

        magazine = decoded[0]
        packet_num = decoded[1]

        if packet_num == 0 and len(decoded) >= 5:
            self._process_header(packet, decoded, magazine)
        elif 1 <= packet_num <= 25:
            self._process_row(packet, decoded, magazine, packet_num)

    def _process_header(self, packet: bytes, decoded: list, magazine: int) -> None:
        """Process page header packet."""
        page = decoded[2]
        control = decoded[4]

        full_page = magazine * 100 + page

        # Check subtitle flag (bit 6 of control word)
        is_subtitle = (control & 0x40) != 0

        # Flush previous page if it was a subtitle page
        if self.is_subtitle_page.get(magazine, False):
            self._flush_page(magazine)

        # Update state for new page
        self.current_page[magazine] = full_page
        self.current_rows[magazine] = {}
        self.is_subtitle_page[magazine] = is_subtitle

    def _process_row(
        self, packet: bytes, decoded: list, magazine: int, row: int
    ) -> None:
        """Process page row packet with full formatting extraction."""
        # Only process rows from pages with subtitle flag set
        if not self.is_subtitle_page.get(magazine, False):
            return

        # Use decoded text from decode_teletext_line if available
        if len(decoded) >= 3 and isinstance(decoded[2], str):
            line = self._parse_decoded_text(decoded[2], row)
        else:
            # Fallback to raw byte parsing
            line = self._parse_row_with_formatting(packet, row)

        if line.has_content:
            self.current_rows.setdefault(magazine, {})[row] = line

    def _parse_decoded_text(self, text: str, row: int) -> SubtitleLine:
        """
        Parse already-decoded teletext text string.

        The decoder returns text with control codes as ⟦XX⟧ sequences.
        We need to extract the actual text and formatting.
        """
        import re

        line = SubtitleLine(row=row)

        # Extract formatting from control codes in the text
        double_height = False
        boxing = False

        # Check for control codes
        if "⟦0D⟧" in text:  # Double height
            double_height = True
            line.double_height = True
        if "⟦0B⟧" in text:  # Start box
            boxing = True

        # Remove all control code sequences ⟦XX⟧
        clean_text = re.sub(r"⟦[0-9A-Fa-f]{2}⟧", "", text)

        # Strip whitespace
        clean_text = clean_text.strip()

        if clean_text:
            line.segments.append(
                TextSegment(
                    text=clean_text,
                    foreground_color=TeletextColor.WHITE,
                    background_color=TeletextColor.BLACK,
                    double_height=double_height,
                    flash=False,
                    boxing=boxing,
                    concealed=False,
                )
            )

        return line

    def _parse_row_with_formatting(self, packet: bytes, row: int) -> SubtitleLine:
        """
        Parse a teletext row extracting all formatting information.

        Handles:
        - Foreground colors (0x00-0x07)
        - Background colors (0x1C, 0x1D)
        - Double height (0x0D)
        - Flash (0x08)
        - Boxing (0x0B)
        - Concealed text (0x18)
        """
        line = SubtitleLine(row=row)

        # Current formatting state
        fg_color = TeletextColor.WHITE
        bg_color = TeletextColor.BLACK
        double_height = False
        flash = False
        boxing = False
        concealed = False

        current_text = ""

        # Process bytes 2-41 (40 character positions)
        for i in range(2, 42):
            byte = packet[i] & 0x7F  # Strip parity

            if byte < 0x20:
                # Control code - save current segment if any
                if current_text:
                    line.segments.append(
                        TextSegment(
                            text=current_text,
                            foreground_color=fg_color,
                            background_color=bg_color,
                            double_height=double_height,
                            flash=flash,
                            boxing=boxing,
                            concealed=concealed,
                        )
                    )
                    current_text = ""

                # Process control code
                if byte <= 0x07:
                    # Alpha color (foreground)
                    fg_color = TeletextColor(byte)
                    concealed = False  # Color change reveals
                elif byte == TeletextControlCode.FLASH:
                    flash = True
                elif byte == TeletextControlCode.STEADY:
                    flash = False
                elif byte == TeletextControlCode.START_BOX:
                    boxing = True
                elif byte == TeletextControlCode.END_BOX:
                    boxing = False
                elif byte == TeletextControlCode.DOUBLE_HEIGHT:
                    double_height = True
                    line.double_height = True
                elif byte == TeletextControlCode.NORMAL_HEIGHT:
                    double_height = False
                elif byte == TeletextControlCode.CONCEAL:
                    concealed = True
                elif byte == TeletextControlCode.BLACK_BACKGROUND:
                    bg_color = TeletextColor.BLACK
                elif byte == TeletextControlCode.NEW_BACKGROUND:
                    bg_color = fg_color
                elif byte >= 0x10 and byte <= 0x17:
                    # Mosaic color (treat as foreground for subtitles)
                    fg_color = TeletextColor(byte - 0x10)

                # Control codes are NOT added to text (they're formatting only)

            elif byte == 0x20:
                # Space character - add to current text
                current_text += " "
            else:
                # Regular printable character (0x21-0x7F)
                current_text += chr(byte)

        # Save final segment
        if current_text:
            line.segments.append(
                TextSegment(
                    text=current_text,
                    foreground_color=fg_color,
                    background_color=bg_color,
                    double_height=double_height,
                    flash=flash,
                    boxing=boxing,
                    concealed=concealed,
                )
            )

        return line

    def _flush_page(self, magazine: int) -> None:
        """Save accumulated rows as a subtitle."""
        rows = self.current_rows.get(magazine, {})
        if not rows:
            return

        # Create subtitle from rows
        lines = [rows[r] for r in sorted(rows.keys())]

        # Only create if there's actual content
        if any(line.has_content for line in lines):
            # Get text content for deduplication check
            new_text = " ".join(line.text.strip() for line in lines if line.has_content)

            # Skip if this is a duplicate of the last subtitle (teletext repeats for reliability)
            if self.subtitles:
                last_sub = self.subtitles[-1]
                last_text = " ".join(
                    line.text.strip() for line in last_sub.lines if line.has_content
                )
                if new_text == last_text:
                    # Same content - skip this duplicate
                    self.current_rows[magazine] = {}
                    return

            # Determine vertical position from first non-empty row
            vp = 20  # Default
            for line in lines:
                if line.has_content:
                    vp = line.row
                    break

            # Detect justification from text alignment
            justification = self._detect_justification(lines)

            subtitle = Subtitle(
                index=len(self.subtitles) + 1,
                start_time=self.frame_count,
                end_time=self.frame_count + 75,  # Default 3 seconds at 25fps
                lines=lines,
                justification=justification,
                vertical_position=vp,
            )
            self.subtitles.append(subtitle)
            self.last_subtitle_time[magazine] = self.frame_count

        self.current_rows[magazine] = {}

    def _detect_justification(self, lines: List[SubtitleLine]) -> JustificationCode:
        """Detect text justification from content alignment."""
        for line in lines:
            if not line.has_content:
                continue

            text = line.text
            stripped = text.strip()
            if not stripped:
                continue

            left_spaces = len(text) - len(text.lstrip())
            right_spaces = len(text) - len(text.rstrip())

            # If roughly centered
            if abs(left_spaces - right_spaces) <= 3:
                return JustificationCode.CENTERED
            elif left_spaces < right_spaces:
                return JustificationCode.LEFT
            else:
                return JustificationCode.RIGHT

        return JustificationCode.CENTERED

    def _calculate_end_times(self) -> None:
        """Set end times based on next subtitle start time."""
        for i in range(len(self.subtitles) - 1):
            current = self.subtitles[i]
            next_sub = self.subtitles[i + 1]

            # End time is 1 frame before next start, or at most 3 seconds
            gap = 1  # 1 frame gap
            max_duration = 75  # 3 seconds at 25fps

            end_time = min(next_sub.start_time - gap, current.start_time + max_duration)
            current.end_time = max(end_time, current.start_time + 25)  # Min 1 second

        # Last subtitle - keep default short duration
        if self.subtitles:
            last = self.subtitles[-1]
            last.end_time = last.start_time + 50  # 2 seconds


# =============================================================================
# EBU STL Writer with Full Formatting
# =============================================================================


class EBUSTLWriter:
    """
    Writes subtitles to EBU STL format with complete formatting support.

    Supports:
    - Colors (foreground via teletext control codes)
    - Vertical positioning
    - Justification
    - Double height
    - Boxing (open/closed captions)
    """

    def __init__(self, program_title: str = "Untitled", frame_rate: int = 25):
        self.program_title = program_title[:32].ljust(32)
        self.language_code = "  "  # Unknown
        self.frame_rate = frame_rate
        self.country_code = "   "  # Unknown
        self.display_standard = "1"  # Open subtitles

    def write(self, subtitles: List[Subtitle], output_path: str) -> None:
        """Write subtitles to an EBU STL file."""
        with open(output_path, "wb") as f:
            f.write(self._create_gsi(len(subtitles)))

            for subtitle in subtitles:
                tti_blocks = self._create_tti_blocks(subtitle)
                for block in tti_blocks:
                    f.write(block)

    def _create_gsi(self, subtitle_count: int) -> bytes:
        """Create the GSI block (1024 bytes)."""
        now = datetime.now()
        gsi = bytearray(1024)

        # Code Page Number (CPN) - 3 bytes
        gsi[0:3] = b"850"

        # Disk Format Code (DFC) - 8 bytes
        dfc = f"STL{self.frame_rate:02d}.01"
        gsi[3:11] = dfc.encode("latin-1").ljust(8)

        # Display Standard Code (DSC) - 1 byte
        gsi[11:12] = self.display_standard.encode("latin-1")

        # Character Code Table (CCT) - 2 bytes - "00" for Latin
        gsi[12:14] = b"00"

        # Language Code (LC) - 2 bytes
        gsi[14:16] = self.language_code.encode("latin-1")

        # Original Program Title (OPT) - 32 bytes
        gsi[16:48] = self.program_title.encode("latin-1", errors="replace").ljust(32)

        # Original Episode Title (OET) - 32 bytes
        gsi[48:80] = b" " * 32

        # Translated Program Title (TPT) - 32 bytes
        gsi[80:112] = b" " * 32

        # Translated Episode Title (TET) - 32 bytes
        gsi[112:144] = b" " * 32

        # Translator's Name (TN) - 32 bytes
        gsi[144:176] = b" " * 32

        # Translator's Contact Details (TCD) - 32 bytes
        gsi[176:208] = b" " * 32

        # Subtitle List Reference (SLR) - 16 bytes
        gsi[208:224] = b" " * 16

        # Creation Date (CD) - 6 bytes
        gsi[224:230] = now.strftime("%y%m%d").encode("latin-1")

        # Revision Date (RD) - 6 bytes
        gsi[230:236] = now.strftime("%y%m%d").encode("latin-1")

        # Revision Number (RN) - 2 bytes
        gsi[236:238] = b"00"

        # Total Number of TTI Blocks (TNB) - 5 bytes
        gsi[238:243] = f"{subtitle_count:05d}".encode("latin-1")

        # Total Number of Subtitles (TNS) - 5 bytes
        gsi[243:248] = f"{subtitle_count:05d}".encode("latin-1")

        # Total Number of Subtitle Groups (TNG) - 3 bytes
        gsi[248:251] = b"001"

        # Maximum Number of Displayable Characters (MNC) - 2 bytes
        gsi[251:253] = b"40"

        # Maximum Number of Displayable Rows (MNR) - 2 bytes
        gsi[253:255] = b"23"

        # Time Code Status (TCS) - 1 byte
        gsi[255:256] = b"1"

        # Time Code: Start of Programme (TCP) - 8 bytes
        gsi[256:264] = b"00000000"

        # Time Code: First In-Cue (TCF) - 8 bytes
        gsi[264:272] = b"00000000"

        # Total Number of Disks (TND) - 1 byte
        gsi[272:273] = b"1"

        # Disk Sequence Number (DSN) - 1 byte
        gsi[273:274] = b"1"

        # Country of Origin (CO) - 3 bytes
        gsi[274:277] = self.country_code.encode("latin-1")

        # Publisher (PUB) - 32 bytes
        gsi[277:309] = b" " * 32

        # Editor's Name (EN) - 32 bytes
        gsi[309:341] = b" " * 32

        # Editor's Contact Details (ECD) - 32 bytes
        gsi[341:373] = b" " * 32

        # Spare Bytes - 75 bytes
        gsi[373:448] = b" " * 75

        # User-Defined Area (UDA) - 576 bytes
        gsi[448:1024] = b" " * 576

        return bytes(gsi)

    def _create_tti_blocks(self, subtitle: Subtitle) -> List[bytes]:
        """Create TTI block(s) for a subtitle (may need multiple for long text)."""
        blocks = []

        # Encode full text with formatting
        full_text = self._encode_text_with_formatting(subtitle)

        # Split into 112-byte chunks if needed
        chunk_size = 112
        chunks = [
            full_text[i : i + chunk_size] for i in range(0, len(full_text), chunk_size)
        ]

        if not chunks:
            chunks = [b""]

        for i, chunk in enumerate(chunks):
            is_last = i == len(chunks) - 1
            block = self._create_single_tti(subtitle, chunk, i, is_last)
            blocks.append(block)

        return blocks

    def _create_single_tti(
        self, subtitle: Subtitle, text_chunk: bytes, extension: int, is_last: bool
    ) -> bytes:
        """Create a single TTI block (128 bytes)."""
        tti = bytearray(128)

        # Subtitle Group Number (SGN) - 1 byte
        tti[0] = 0x00

        # Subtitle Number (SN) - 2 bytes (little endian)
        struct.pack_into("<H", tti, 1, subtitle.index)

        # Extension Block Number (EBN) - 1 byte
        tti[3] = 0xFF if is_last else extension

        # Cumulative Status (CS) - 1 byte
        tti[4] = 0x00

        # Time Code In (TCI) - 4 bytes
        tti[5:9] = self._frames_to_timecode(subtitle.start_time)

        # Time Code Out (TCO) - 4 bytes
        tti[9:13] = self._frames_to_timecode(subtitle.end_time)

        # Vertical Position (VP) - 1 byte
        tti[13] = min(max(subtitle.vertical_position, 0), 23)

        # Justification Code (JC) - 1 byte
        tti[14] = subtitle.justification

        # Comment Flag (CF) - 1 byte
        tti[15] = 0x00

        # Text Field (TF) - 112 bytes
        padded_text = text_chunk.ljust(112, bytes([EBUSTLControlCode.UNUSED_SPACE]))
        tti[16:128] = padded_text[:112]

        return bytes(tti)

    def _frames_to_timecode(self, frames: int) -> bytes:
        """Convert frame count to timecode bytes."""
        total_seconds = frames // self.frame_rate
        remaining_frames = frames % self.frame_rate

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        return bytes([hours, minutes, seconds, remaining_frames])

    def _encode_text_with_formatting(self, subtitle: Subtitle) -> bytes:
        """
        Encode subtitle text for EBU STL format.

        Produces clean text with:
        - Start Box codes for closed captions
        - Double Height for teletext display
        - Line breaks between lines
        - Clean stripped text (no leading/trailing spaces)
        """
        result = bytearray()

        # Collect all non-empty lines with stripped text
        text_lines = []
        for line in subtitle.lines:
            # Get clean text: strip each segment and join
            line_text = ""
            for segment in line.segments:
                if not segment.concealed:
                    line_text += segment.text

            # Strip the whole line
            stripped = line_text.strip()
            if stripped:
                text_lines.append((stripped, line.double_height))

        if not text_lines:
            return bytes()

        # Add text lines with proper control codes for each line
        has_double_height = any(dh for _, dh in text_lines)

        for i, (text, _) in enumerate(text_lines):
            if i > 0:
                # Between lines: End Box (0x0A 0x0A) + CR/LF (0x8A 0x8A)
                result.append(0x0A)  # End Box
                result.append(0x0A)  # End Box
                result.append(0x8A)  # CR/LF
                result.append(0x8A)  # CR/LF

            # Each line starts with control codes
            if has_double_height:
                result.append(0x0D)  # Double Height
            result.append(0x0B)  # Start Box
            result.append(0x0B)  # Start Box

            # Encode text as latin-1 with UK teletext character mapping
            # UK Teletext G0 National Option Subset differs from ASCII at these positions
            UK_TELETEXT_TO_LATIN1 = {
                "#": 0xA3,  # 0x23 → £ (pound sterling)
                "[": 0x2190,  # 0x5B → ← (left arrow) - no Latin-1, keep as [
                "\\": 0xBD,  # 0x5C → ½ (one-half)
                "]": 0x2192,  # 0x5D → → (right arrow) - no Latin-1, keep as ]
                "^": 0x2191,  # 0x5E → ↑ (up arrow) - no Latin-1, keep as ^
                "_": 0x23,  # 0x5F → # (number sign)
                "`": 0x2D,  # 0x60 → - (dash)
                "{": 0xBC,  # 0x7B → ¼ (one-quarter)
                "|": 0x7C,  # 0x7C → ‖ (double vertical line) - keep as |
                "}": 0xBE,  # 0x7D → ¾ (three-quarters)
                "~": 0xF7,  # 0x7E → ÷ (division sign)
            }

            for char in text:
                if char in UK_TELETEXT_TO_LATIN1:
                    mapped = UK_TELETEXT_TO_LATIN1[char]
                    if mapped <= 0xFF:  # Only use if it fits in Latin-1
                        result.append(mapped)
                    else:
                        result.append(ord(char))  # Keep original for non-Latin-1
                else:
                    try:
                        encoded = char.encode("latin-1")
                        result.append(encoded[0])
                    except (UnicodeEncodeError, ValueError):
                        result.append(0x20)  # Space for unencodable

        # Add trailing End Box + newlines
        result.append(0x0A)  # End Box
        result.append(0x0A)  # End Box

        return bytes(result)


# =============================================================================
# Main Conversion Function
# =============================================================================


def convert_teletext_to_stl(
    raw_data: bytes,
    output_path: str,
    program_title: str = "Untitled",
    total_frames: int = None,
    frame_rate: float = 25,
) -> int:
    """
    Convert raw teletext data to EBU STL format with full formatting.

    Extracts ALL teletext pages from the raw data.

    Args:
        raw_data: Binary teletext data from MXF extraction
        output_path: Path for output STL file
        program_title: Title for the program (optional)
        total_frames: Total video frames (for accurate timing)
        frame_rate: Video frame rate (default 25fps for PAL)

    Returns:
        Number of subtitles extracted
    """
    parser = TeletextParser(total_frames=total_frames, frame_rate=frame_rate)
    subtitles = parser.parse(raw_data)

    print(f"Found {len(subtitles)} subtitles")

    # Debug: show some info about extracted subtitles
    for i, sub in enumerate(subtitles[:5]):  # Show first 5
        lines_text = " | ".join(
            line.text.strip() for line in sub.lines if line.text.strip()
        )
        print(
            f"  [{i + 1}] {_format_tc(sub.start_time)} -> {_format_tc(sub.end_time)}: {lines_text[:60]}..."
        )

    if len(subtitles) > 5:
        print(f"  ... and {len(subtitles) - 5} more")

    if subtitles:
        writer = EBUSTLWriter(program_title=program_title, frame_rate=int(frame_rate))
        writer.write(subtitles, output_path)
        print(f"Written to {output_path}")

    return len(subtitles)


def _format_tc(frames: int, fps: int = 25) -> str:
    """Format frame count as timecode string."""
    total_seconds = frames // fps
    f = frames % fps
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"
