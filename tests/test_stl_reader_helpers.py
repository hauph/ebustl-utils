from ebustl_utils.STLReader.helpers import (
    format_timecode_from_seconds,
    decode_ebu_stl_text,
)
from ebustl_utils.models import (
    EBUSTLControlCode,
)

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
# Tests for styled segments
# =============================================================================


class TestDecodeEbuStlTextSegments:
    """Tests for inline styled segments."""

    def test_single_style_returns_one_segment(self):
        """Single style text returns one segment."""
        text_raw = make_tti_text(bytes([EBUSTLControlCode.ALPHA_RED]), b"Red text")

        result = decode_ebu_stl_text(text_raw)

        assert len(result["segments"]) == 1
        assert result["segments"][0].text == "Red text"
        assert result["segments"][0].color == "red"

    def test_multiple_colors_creates_segments(self):
        """Multiple color codes create separate segments."""
        text_raw = make_tti_text(
            bytes([EBUSTLControlCode.ALPHA_BLUE]),
            b"blue ",
            bytes([EBUSTLControlCode.ALPHA_GREEN]),
            b"green",
        )

        result = decode_ebu_stl_text(text_raw)

        assert len(result["segments"]) == 2
        assert result["segments"][0].text == "blue "
        assert result["segments"][0].color == "blue"
        assert result["segments"][1].text == "green"
        assert result["segments"][1].color == "green"

    def test_color_resets_on_newline(self):
        """Color resets to white after newline (Adobe Premiere behavior)."""
        text_raw = make_tti_text(
            bytes([EBUSTLControlCode.ALPHA_GREEN]),
            b"green",
            bytes([EBUSTLControlCode.NEWLINE]),
            b"white",
        )

        result = decode_ebu_stl_text(text_raw)

        assert result["text"] == "green\nwhite"
        # First segment: green text with newline
        assert result["segments"][0].text == "green\n"
        assert result["segments"][0].color == "green"
        # Second segment: white text (color reset)
        assert result["segments"][1].text == "white"
        assert result["segments"][1].color is None  # None means white/default

    def test_consecutive_same_style_merged(self):
        """Consecutive segments with same style are merged."""
        # Double height on, then newline (resets color but not double_height)
        # Both segments should have double_height=True and color=None
        text_raw = make_tti_text(
            bytes([EBUSTLControlCode.DOUBLE_HEIGHT]),
            b"Line1",
            bytes([EBUSTLControlCode.NEWLINE]),
            b"Line2",
        )

        result = decode_ebu_stl_text(text_raw)

        # Both lines have same style (double_height=True, color=None)
        # So they should be merged into one segment
        assert len(result["segments"]) == 1
        assert result["segments"][0].text == "Line1\nLine2"
        assert result["segments"][0].double_height is True

    def test_style_change_creates_new_segment(self):
        """Style change mid-text creates new segment."""
        text_raw = make_tti_text(
            b"normal ",
            bytes([EBUSTLControlCode.ITALIC_ON]),
            b"italic",
        )

        result = decode_ebu_stl_text(text_raw)

        assert len(result["segments"]) == 2
        assert result["segments"][0].text == "normal "
        assert result["segments"][0].italic is False
        assert result["segments"][1].text == "italic"
        assert result["segments"][1].italic is True

    def test_multiple_style_attributes(self):
        """Multiple style attributes tracked per segment."""
        text_raw = make_tti_text(
            bytes([EBUSTLControlCode.ALPHA_RED, EBUSTLControlCode.ITALIC_ON]),
            b"red italic",
        )

        result = decode_ebu_stl_text(text_raw)

        assert len(result["segments"]) == 1
        assert result["segments"][0].text == "red italic"
        assert result["segments"][0].color == "red"
        assert result["segments"][0].italic is True
