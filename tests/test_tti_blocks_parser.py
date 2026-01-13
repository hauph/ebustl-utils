import io
from ebustl_utils.STLReader.parsers.tti_parser import parse_tti_blocks
from helpers_for_testing import make_tti_block


# =============================================================================
# Helper to create buffer from TTI blocks
# =============================================================================


def make_tti_buffer(tti_blocks: list) -> io.BytesIO:
    """Create a BytesIO buffer from TTI blocks."""
    data = b"".join(tti_blocks)
    return io.BytesIO(data)


# =============================================================================
# Tests for parse_tti_blocks - Basic Parsing
# =============================================================================


class TestParseTTIBlocksBasic:
    """Tests for basic TTI block parsing."""

    def test_parse_single_block(self):
        """Should parse a single TTI block into a caption."""
        tti = make_tti_block(text=b"Hello World")
        buffer = make_tti_buffer([tti])

        captions = parse_tti_blocks(buffer, fps=25.0)

        assert len(captions) == 1
        assert "Hello World" in captions[0].text

    def test_parse_multiple_blocks(self):
        """Should parse multiple TTI blocks into multiple captions."""
        tti1 = make_tti_block(sn=1, text=b"First caption")
        tti2 = make_tti_block(sn=2, text=b"Second caption")
        buffer = make_tti_buffer([tti1, tti2])

        captions = parse_tti_blocks(buffer, fps=25.0)

        assert len(captions) == 2
        assert "First caption" in captions[0].text
        assert "Second caption" in captions[1].text

    def test_parse_empty_buffer(self):
        """Should return empty list for empty buffer."""
        buffer = io.BytesIO(b"")

        captions = parse_tti_blocks(buffer, fps=25.0)

        assert captions == []

    def test_parse_partial_block_ignored(self):
        """Should ignore trailing partial blocks (< 128 bytes)."""
        tti = make_tti_block(text=b"Complete block")
        partial = b"x" * 50  # Partial block
        buffer = make_tti_buffer([tti])
        buffer.write(partial)
        buffer.seek(0)

        captions = parse_tti_blocks(buffer, fps=25.0)

        assert len(captions) == 1


# =============================================================================
# Tests for parse_tti_blocks - Timing
# =============================================================================


class TestParseTTIBlocksTiming:
    """Tests for TTI block timing extraction."""

    def test_timing_in_microseconds(self):
        """Caption timing should be in microseconds."""
        # TCI: 00:00:01:00 (1 second), TCO: 00:00:03:00 (3 seconds)
        tti = make_tti_block(
            tci=(0, 0, 1, 0),
            tco=(0, 0, 3, 0),
        )
        buffer = make_tti_buffer([tti])

        captions = parse_tti_blocks(buffer, fps=25.0)

        assert captions[0].start == 1_000_000  # 1 second in microseconds
        assert captions[0].end == 3_000_000  # 3 seconds in microseconds

    def test_timing_with_frames(self):
        """Should correctly include frame portion in timing."""
        # TCI: 00:00:01:12 (1 second + 12 frames at 25fps = 1.48 seconds)
        tti = make_tti_block(
            tci=(0, 0, 1, 12),
            tco=(0, 0, 2, 0),
        )
        buffer = make_tti_buffer([tti])

        captions = parse_tti_blocks(buffer, fps=25.0)

        # 1 second + 12/25 frames = 1.48 seconds = 1,480,000 microseconds
        assert captions[0].start == 1_480_000

    def test_timecode_format(self):
        """Should generate proper timecode strings."""
        tti = make_tti_block(
            tci=(1, 30, 45, 10),  # 01:30:45:10
            tco=(1, 30, 47, 0),
        )
        buffer = make_tti_buffer([tti])

        captions = parse_tti_blocks(buffer, fps=25.0)

        assert captions[0].start_timecode == "01:30:45;10"


# =============================================================================
# Tests for parse_tti_blocks - Justification
# =============================================================================


class TestParseTTIBlocksJustification:
    """Tests for justification code parsing."""

    def test_justification_left(self):
        """Should parse left justification."""
        tti = make_tti_block(jc=0x01, text=b"Left aligned")
        buffer = make_tti_buffer([tti])

        captions = parse_tti_blocks(buffer, fps=25.0)

        assert captions[0].justification == "left"

    def test_justification_center(self):
        """Should parse center justification."""
        tti = make_tti_block(jc=0x02, text=b"Centered")
        buffer = make_tti_buffer([tti])

        captions = parse_tti_blocks(buffer, fps=25.0)

        assert captions[0].justification == "center"

    def test_justification_right(self):
        """Should parse right justification."""
        tti = make_tti_block(jc=0x03, text=b"Right aligned")
        buffer = make_tti_buffer([tti])

        captions = parse_tti_blocks(buffer, fps=25.0)

        assert captions[0].justification == "right"

    def test_justification_unchanged(self):
        """Should return None for unchanged justification."""
        tti = make_tti_block(jc=0x00, text=b"No preference")
        buffer = make_tti_buffer([tti])

        captions = parse_tti_blocks(buffer, fps=25.0)

        assert captions[0].justification is None


# =============================================================================
# Tests for parse_tti_blocks - Vertical Position
# =============================================================================


class TestParseTTIBlocksVerticalPosition:
    """Tests for vertical position parsing."""

    def test_vertical_position_extracted(self):
        """Should extract vertical position from TTI block."""
        tti = make_tti_block(vp=15, text=b"Test")
        buffer = make_tti_buffer([tti])

        captions = parse_tti_blocks(buffer, fps=25.0)

        assert captions[0].vertical_position == 15

    def test_vertical_position_valid_range(self):
        """Should accept vertical positions 0-23."""
        tti = make_tti_block(vp=0, text=b"Top")
        buffer = make_tti_buffer([tti])

        captions = parse_tti_blocks(buffer, fps=25.0)

        assert captions[0].vertical_position == 0

    def test_vertical_position_invalid_becomes_none(self):
        """Should return None for invalid vertical positions (> 23)."""
        tti = make_tti_block(vp=30, text=b"Invalid position")
        buffer = make_tti_buffer([tti])

        captions = parse_tti_blocks(buffer, fps=25.0)

        assert captions[0].vertical_position is None


# =============================================================================
# Tests for parse_tti_blocks - Multi-block Subtitles
# =============================================================================


class TestParseTTIBlocksMultiBlock:
    """Tests for multi-block subtitle support."""

    def test_single_block_cs_00(self):
        """CS=0x00 indicates a single-block subtitle."""
        tti = make_tti_block(sn=1, cs=0x00, text=b"Single block")
        buffer = make_tti_buffer([tti])

        captions = parse_tti_blocks(buffer, fps=25.0)

        assert len(captions) == 1
        assert "Single block" in captions[0].text

    def test_multi_block_first_intermediate_last(self):
        """Should combine text from first(0x01), intermediate(0x02), and last(0x03) blocks."""
        # Create multi-block subtitle with same SN
        tti1 = make_tti_block(sn=1, cs=0x01, text=b"First part ")
        tti2 = make_tti_block(sn=1, cs=0x02, text=b"middle part ")
        tti3 = make_tti_block(sn=1, cs=0x03, text=b"last part")
        buffer = make_tti_buffer([tti1, tti2, tti3])

        captions = parse_tti_blocks(buffer, fps=25.0)

        assert len(captions) == 1
        assert "First part" in captions[0].text
        assert "middle part" in captions[0].text
        assert "last part" in captions[0].text


# =============================================================================
# Tests for parse_tti_blocks - Text Decoding
# =============================================================================


class TestParseTTIBlocksTextDecoding:
    """Tests for text decoding functionality."""

    def test_strips_whitespace(self):
        """Should strip leading/trailing whitespace from text."""
        tti = make_tti_block(text=b"  Text with spaces  ")
        buffer = make_tti_buffer([tti])

        captions = parse_tti_blocks(buffer, fps=25.0)

        assert captions[0].text == "Text with spaces"

    def test_empty_text_skipped(self):
        """Should skip blocks with only whitespace."""
        # Create a TTI block with only spaces/padding
        tti = bytearray(128)
        tti[0] = 0  # SGN
        tti[1:3] = b"\x00\x01"  # SN
        tti[3] = 0xFF  # EBN
        tti[4] = 0x00  # CS - single
        tti[5:9] = bytes([0, 0, 1, 0])  # TCI
        tti[9:13] = bytes([0, 0, 2, 0])  # TCO
        tti[13] = 20  # VP
        tti[14] = 2  # JC
        tti[16:128] = b" " * 112  # Empty text (spaces only)
        buffer = make_tti_buffer([bytes(tti)])

        captions = parse_tti_blocks(buffer, fps=25.0)

        assert len(captions) == 0

    def test_cct_parameter_used(self):
        """Should pass CCT parameter for character decoding."""
        # Just verify it doesn't crash with different CCT values
        tti = make_tti_block(text=b"Latin text")
        buffer = make_tti_buffer([tti])

        captions = parse_tti_blocks(buffer, fps=25.0, cct="00")

        assert len(captions) == 1


# =============================================================================
# Tests for parse_tti_blocks - Frame Rate
# =============================================================================


class TestParseTTIBlocksFrameRate:
    """Tests for different frame rates."""

    def test_fps_25(self):
        """Should calculate timing correctly at 25 fps."""
        tti = make_tti_block(tci=(0, 0, 0, 25), tco=(0, 0, 1, 0))
        buffer = make_tti_buffer([tti])

        captions = parse_tti_blocks(buffer, fps=25.0)

        # 25 frames at 25fps = 1 second
        assert captions[0].start == 1_000_000

    def test_fps_30(self):
        """Should calculate timing correctly at 30 fps."""
        tti = make_tti_block(tci=(0, 0, 0, 15), tco=(0, 0, 1, 0))
        buffer = make_tti_buffer([tti])

        captions = parse_tti_blocks(buffer, fps=30.0)

        # 15 frames at 30fps = 0.5 seconds = 500,000 microseconds
        assert captions[0].start == 500_000
