from ebustl_utils.helpers import (
    extract_teletext_from_vanc,
    TeletextParser,
    EBUSTLWriter,
    format_timecode_from_seconds,
    decode_ebu_stl_text,
    _format_tc,
)
from ebustl_utils.models import (
    Subtitle,
    SubtitleLine,
    TextSegment,
    TeletextColor,
    JustificationCode,
    EBUSTLControlCode,
)

from helpers_for_testing import TELETEXT_SYNC


# =============================================================================
# Tests for extract_teletext_from_vanc
# =============================================================================


# Padding needed because extract function checks offset < len(raw_data) - 45
VANC_PADDING = bytes([0x00] * 10)


def make_teletext_packet(byte1: int, byte2: int, fill: int = 0x20) -> bytes:
    """Create a 42-byte teletext packet with given header bytes and fill."""
    return bytes([byte1, byte2] + [fill] * 40)


class TestExtractTeletextFromVanc:
    """Tests for VANC teletext packet extraction."""

    def test_extract_single_packet(self):
        """Extract a single teletext packet from VANC data."""
        packet_data = make_teletext_packet(0x01, 0x02)
        raw_data = TELETEXT_SYNC + packet_data + VANC_PADDING

        packets = extract_teletext_from_vanc(raw_data)

        assert len(packets) == 1
        assert packets[0][0] == packet_data
        assert packets[0][1] == 0  # packet index

    def test_extract_multiple_packets(self):
        """Extract multiple teletext packets from VANC data."""
        packet1 = make_teletext_packet(0x01, 0x01, fill=0x41)
        packet2 = make_teletext_packet(0x02, 0x02, fill=0x42)

        raw_data = TELETEXT_SYNC + packet1 + TELETEXT_SYNC + packet2 + VANC_PADDING

        packets = extract_teletext_from_vanc(raw_data)

        assert len(packets) == 2
        assert packets[0][0] == packet1
        assert packets[1][0] == packet2
        assert packets[0][1] == 0
        assert packets[1][1] == 1

    def test_no_sync_pattern(self):
        """Return empty list when no sync pattern found."""
        raw_data = bytes([0x00] * 100)

        packets = extract_teletext_from_vanc(raw_data)

        assert len(packets) == 0

    def test_incomplete_packet(self):
        """Skip incomplete packets after sync pattern."""
        incomplete = bytes([0x01] * 10)  # Only 10 bytes instead of 42
        raw_data = TELETEXT_SYNC + incomplete

        packets = extract_teletext_from_vanc(raw_data)

        assert len(packets) == 0


# =============================================================================
# Tests for format_timecode_from_seconds
# =============================================================================


class TestFormatTimecodeFromSeconds:
    """Tests for timecode formatting utility."""

    def test_zero_seconds(self):
        """Format 0 seconds."""
        result = format_timecode_from_seconds(0, 25)
        assert result == "00:00:00;00"

    def test_simple_seconds(self):
        """Format simple seconds value."""
        result = format_timecode_from_seconds(5, 25)
        assert result == "00:00:05;00"

    def test_with_frames(self):
        """Format seconds with fractional frames."""
        # 5.5 seconds at 25fps = 5 seconds + 12.5 frames (rounds to 13)
        result = format_timecode_from_seconds(5.52, 25)
        assert result == "00:00:05;13"

    def test_minutes(self):
        """Format minutes value."""
        result = format_timecode_from_seconds(125, 25)  # 2:05
        assert result == "00:02:05;00"

    def test_hours(self):
        """Format hours value."""
        result = format_timecode_from_seconds(3661, 25)  # 1:01:01
        assert result == "01:01:01;00"

    def test_negative_clamps_to_zero(self):
        """Negative seconds should clamp to zero."""
        result = format_timecode_from_seconds(-5, 25)
        assert result == "00:00:00;00"


# =============================================================================
# Tests for _format_tc (internal frame formatter)
# =============================================================================


class TestFormatTc:
    """Tests for frame-to-timecode formatting."""

    def test_zero_frames(self):
        """Format 0 frames."""
        result = _format_tc(0, 25)
        assert result == "00:00:00:00"

    def test_simple_frames(self):
        """Format simple frame count."""
        result = _format_tc(75, 25)  # 3 seconds
        assert result == "00:00:03:00"

    def test_with_remaining_frames(self):
        """Format with remaining frames."""
        result = _format_tc(88, 25)  # 3 seconds + 13 frames
        assert result == "00:00:03:13"

    def test_minutes_and_hours(self):
        """Format complex timecode."""
        # 1 hour, 2 minutes, 3 seconds, 10 frames
        frames = (1 * 3600 + 2 * 60 + 3) * 25 + 10
        result = _format_tc(frames, 25)
        assert result == "01:02:03:10"


# =============================================================================
# Tests for decode_ebu_stl_text
# =============================================================================

# TTI text field is 112 bytes
TTI_TEXT_FIELD_SIZE = 112


def make_tti_text(*parts: bytes) -> bytes:
    """Create a 112-byte TTI text field from parts, padded with unused space."""
    content = b"".join(parts)
    padding_size = TTI_TEXT_FIELD_SIZE - len(content)
    return content + bytes([EBUSTLControlCode.UNUSED_SPACE] * padding_size)


class TestDecodeEbuStlText:
    """Tests for TTI text field decoding."""

    def test_simple_text(self):
        """Decode simple ASCII text."""
        text_raw = make_tti_text(b"Hello")

        result = decode_ebu_stl_text(text_raw)

        assert result["text"] == "Hello"
        assert result["italic"] is False
        assert result["bold"] is False

    def test_italic_text(self):
        """Decode italic formatted text."""
        # Note: decode_ebu_stl_text tracks final state, so omit ITALIC_OFF
        text_raw = make_tti_text(bytes([EBUSTLControlCode.ITALIC_ON]), b"Italic")

        result = decode_ebu_stl_text(text_raw)

        assert result["text"] == "Italic"
        assert result["italic"] is True

    def test_underline_text(self):
        """Decode underlined text."""
        text_raw = make_tti_text(bytes([EBUSTLControlCode.UNDERLINE_ON]), b"Underline")

        result = decode_ebu_stl_text(text_raw)

        assert result["text"] == "Underline"
        assert result["underline"] is True

    def test_double_height(self):
        """Decode double height text."""
        text_raw = make_tti_text(bytes([EBUSTLControlCode.DOUBLE_HEIGHT]), b"Big")

        result = decode_ebu_stl_text(text_raw)

        assert result["text"] == "Big"
        assert result["double_height"] is True

    def test_flash_text(self):
        """Decode flashing text."""
        text_raw = make_tti_text(bytes([EBUSTLControlCode.FLASH]), b"Flash")

        result = decode_ebu_stl_text(text_raw)

        assert result["text"] == "Flash"
        assert result["flash"] is True

    def test_color_code(self):
        """Decode text with color code."""
        text_raw = make_tti_text(bytes([EBUSTLControlCode.ALPHA_RED]), b"Red")

        result = decode_ebu_stl_text(text_raw)

        assert result["text"] == "Red"
        assert result["color"] == "red"

    def test_white_color_returns_none(self):
        """White color (default) returns None."""
        text_raw = make_tti_text(bytes([EBUSTLControlCode.ALPHA_WHITE]), b"White")

        result = decode_ebu_stl_text(text_raw)

        assert result["text"] == "White"
        assert result["color"] is None

    def test_start_box_sets_background(self):
        """Start box control code sets background color."""
        text_raw = make_tti_text(bytes([EBUSTLControlCode.START_BOX]), b"Boxed")

        result = decode_ebu_stl_text(text_raw)

        assert result["text"] == "Boxed"
        assert result["background_color"] == "black"

    def test_newline_handling(self):
        """Decode text with newlines."""
        text_raw = make_tti_text(b"Line1", bytes([EBUSTLControlCode.NEWLINE]), b"Line2")

        result = decode_ebu_stl_text(text_raw)

        assert result["text"] == "Line1\nLine2"

    def test_consecutive_newlines_collapsed(self):
        """Consecutive newlines should be collapsed."""
        text_raw = make_tti_text(
            b"Line1",
            bytes([EBUSTLControlCode.NEWLINE, EBUSTLControlCode.NEWLINE]),
            b"Line2",
        )

        result = decode_ebu_stl_text(text_raw)

        assert result["text"] == "Line1\nLine2"


# =============================================================================
# Tests for EBUSTLWriter
# =============================================================================


class TestEBUSTLWriter:
    """Tests for EBU STL file writer."""

    def test_create_gsi_block_length(self):
        """GSI block should be exactly 1024 bytes."""
        writer = EBUSTLWriter(program_title="Test", frame_rate=25)
        gsi = writer._create_gsi(10)

        assert len(gsi) == 1024

    def test_create_gsi_header_fields(self):
        """GSI block should have correct header fields."""
        writer = EBUSTLWriter(program_title="My Program", frame_rate=25)
        gsi = writer._create_gsi(5)

        # Code Page Number
        assert gsi[0:3] == b"850"
        # Disk Format Code
        assert gsi[3:11] == b"STL25.01"
        # Character Code Table (Latin)
        assert gsi[12:14] == b"00"
        # Total Number of TTI Blocks
        assert gsi[238:243] == b"00005"

    def test_create_tti_block_length(self):
        """TTI block should be exactly 128 bytes."""
        writer = EBUSTLWriter()
        subtitle = Subtitle(
            index=1,
            start_time=0,
            end_time=75,
            lines=[
                SubtitleLine(
                    row=20,
                    segments=[
                        TextSegment(text="Test", foreground_color=TeletextColor.WHITE)
                    ],
                )
            ],
        )

        blocks = writer._create_tti_blocks(subtitle)

        assert len(blocks) == 1
        assert len(blocks[0]) == 128

    def test_frames_to_timecode(self):
        """Convert frames to timecode bytes."""
        writer = EBUSTLWriter(frame_rate=25)

        # 1 hour, 2 minutes, 3 seconds, 10 frames
        frames = (1 * 3600 + 2 * 60 + 3) * 25 + 10
        tc = writer._frames_to_timecode(frames)

        assert tc == bytes([1, 2, 3, 10])

    def test_frames_to_timecode_zero(self):
        """Convert zero frames to timecode."""
        writer = EBUSTLWriter(frame_rate=25)
        tc = writer._frames_to_timecode(0)

        assert tc == bytes([0, 0, 0, 0])


# =============================================================================
# Tests for TeletextParser
# =============================================================================


class TestTeletextParser:
    """Tests for teletext data parser."""

    def test_parser_initialization(self):
        """Parser initializes with correct defaults."""
        parser = TeletextParser(total_frames=1000, frame_rate=25)

        assert parser.total_frames == 1000
        assert parser.frame_rate == 25
        assert parser.subtitles == []

    def test_detect_justification_centered(self):
        """Detect centered text justification."""
        parser = TeletextParser()
        lines = [
            SubtitleLine(
                row=20,
                segments=[TextSegment(text="   centered text   ")],
            )
        ]

        result = parser._detect_justification(lines)

        assert result == JustificationCode.CENTERED

    def test_detect_justification_left(self):
        """Detect left-aligned text justification."""
        parser = TeletextParser()
        lines = [
            SubtitleLine(
                row=20,
                segments=[TextSegment(text="left text          ")],
            )
        ]

        result = parser._detect_justification(lines)

        assert result == JustificationCode.LEFT

    def test_detect_justification_right(self):
        """Detect right-aligned text justification."""
        parser = TeletextParser()
        lines = [
            SubtitleLine(
                row=20,
                segments=[TextSegment(text="          right text")],
            )
        ]

        result = parser._detect_justification(lines)

        assert result == JustificationCode.RIGHT

    def test_detect_justification_empty_lines(self):
        """Empty lines default to centered."""
        parser = TeletextParser()
        lines = [SubtitleLine(row=20, segments=[])]

        result = parser._detect_justification(lines)

        assert result == JustificationCode.CENTERED


# =============================================================================
# Tests for SubtitleLine and TextSegment models
# =============================================================================


class TestSubtitleLine:
    """Tests for SubtitleLine model."""

    def test_text_property(self):
        """Get concatenated text from segments."""
        line = SubtitleLine(
            row=20,
            segments=[
                TextSegment(text="Hello "),
                TextSegment(text="World"),
            ],
        )

        assert line.text == "Hello World"

    def test_has_content_true(self):
        """has_content returns True for non-empty text."""
        line = SubtitleLine(
            row=20,
            segments=[TextSegment(text="Content")],
        )

        assert line.has_content is True

    def test_has_content_false_empty(self):
        """has_content returns False for empty line."""
        line = SubtitleLine(row=20, segments=[])

        assert line.has_content is False

    def test_has_content_false_whitespace(self):
        """has_content returns False for whitespace-only."""
        line = SubtitleLine(
            row=20,
            segments=[TextSegment(text="   ")],
        )

        assert line.has_content is False


class TestSubtitle:
    """Tests for Subtitle model."""

    def test_has_content_true(self):
        """has_content returns True when lines have content."""
        subtitle = Subtitle(
            index=1,
            start_time=0,
            end_time=75,
            lines=[
                SubtitleLine(row=20, segments=[TextSegment(text="Content")]),
            ],
        )

        assert subtitle.has_content is True

    def test_has_content_false(self):
        """has_content returns False when no lines have content."""
        subtitle = Subtitle(
            index=1,
            start_time=0,
            end_time=75,
            lines=[
                SubtitleLine(row=20, segments=[]),
            ],
        )

        assert subtitle.has_content is False
