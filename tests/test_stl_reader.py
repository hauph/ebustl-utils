import pytest
from ebustl_utils.STLReader.STLReader import STLReader

from helpers_for_testing import make_gsi_block, make_stl_file, make_tti_block


# =============================================================================
# Tests for STLReader - Initialization
# =============================================================================


class TestSTLReaderInit:
    """Tests for STLReader initialization."""

    def test_init_without_fps_override(self):
        """STLReader should initialize with None fps."""
        reader = STLReader()

        assert reader.fps is None
        assert reader.captions is None
        assert reader.language is None
        assert reader.gsi is None
        assert reader.result is None

    def test_init_with_fps_override(self):
        """STLReader should store fps_override."""
        reader = STLReader(fps_override=29.97)

        assert reader.fps == 29.97


# =============================================================================
# Tests for STLReader - read() method
# =============================================================================


class TestSTLReaderRead:
    """Tests for STLReader.read() method."""

    def test_read_populates_captions(self):
        """read() should populate captions property."""
        reader = STLReader()
        stl_data = make_stl_file()

        reader.read(stl_data)

        assert reader.captions is not None
        assert isinstance(reader.captions, list)

    def test_read_populates_gsi(self):
        """read() should populate gsi property."""
        reader = STLReader()
        stl_data = make_stl_file()

        reader.read(stl_data)

        assert reader.gsi is not None
        assert isinstance(reader.gsi, dict)

    def test_read_populates_fps(self):
        """read() should populate fps from GSI."""
        reader = STLReader()
        stl_data = make_stl_file()  # Default STL25.01

        reader.read(stl_data)

        assert reader.fps == 25.0

    def test_read_populates_language(self):
        """read() should populate language from GSI."""
        reader = STLReader()
        gsi = make_gsi_block(language_code=b"09")  # English
        stl_data = make_stl_file(gsi=gsi)

        reader.read(stl_data)

        assert reader.language == "en"

    def test_read_populates_result(self):
        """read() should populate result property."""
        reader = STLReader()
        stl_data = make_stl_file()

        reader.read(stl_data)

        assert reader.result is not None
        assert "captions" in reader.result
        assert "fps" in reader.result
        assert "gsi" in reader.result


# =============================================================================
# Tests for STLReader - FPS Override
# =============================================================================


class TestSTLReaderFpsOverride:
    """Tests for STLReader FPS override functionality."""

    def test_fps_override_applied(self):
        """fps_override should be used instead of detected fps."""
        reader = STLReader(fps_override=29.97)
        stl_data = make_stl_file()  # Default STL25.01

        reader.read(stl_data)

        assert reader.fps == 29.97

    def test_fps_from_gsi_when_no_override(self):
        """FPS should come from GSI when no override provided."""
        reader = STLReader()
        gsi = make_gsi_block(dfc=b"STL30.01")
        stl_data = make_stl_file(gsi=gsi)

        reader.read(stl_data)

        assert reader.fps == 30.0


# =============================================================================
# Tests for STLReader - Caption Content
# =============================================================================


class TestSTLReaderCaptionContent:
    """Tests for caption content parsing."""

    def test_caption_text_extracted(self):
        """Caption text should be extracted from TTI block."""
        reader = STLReader()
        tti = make_tti_block(text=b"Test caption text")
        stl_data = make_stl_file(tti_blocks=[tti])

        reader.read(stl_data)

        assert len(reader.captions) == 1
        assert "Test caption text" in reader.captions[0]["text"]

    def test_multiple_captions_extracted(self):
        """Multiple TTI blocks should produce multiple captions."""
        reader = STLReader()
        tti1 = make_tti_block(sn=1, text=b"First caption")
        tti2 = make_tti_block(sn=2, text=b"Second caption")
        stl_data = make_stl_file(tti_blocks=[tti1, tti2])

        reader.read(stl_data)

        assert len(reader.captions) == 2

    def test_caption_has_timing(self):
        """Captions should have timing information."""
        reader = STLReader()
        tti = make_tti_block(
            tci=(0, 0, 1, 0),  # 00:00:01:00
            tco=(0, 0, 2, 0),  # 00:00:02:00
        )
        stl_data = make_stl_file(tti_blocks=[tti])

        reader.read(stl_data)

        caption = reader.captions[0]
        assert "start" in caption
        assert "end" in caption
        assert "start_timecode" in caption
        assert "end_timecode" in caption

    def test_caption_timing_values(self):
        """Caption timing should be correctly calculated in microseconds."""
        reader = STLReader()
        # At 25fps: 1 second = 1,000,000 microseconds
        tti = make_tti_block(
            tci=(0, 0, 1, 0),  # 1 second
            tco=(0, 0, 2, 0),  # 2 seconds
        )
        stl_data = make_stl_file(tti_blocks=[tti])

        reader.read(stl_data)

        caption = reader.captions[0]
        assert caption["start"] == 1_000_000
        assert caption["end"] == 2_000_000


# =============================================================================
# Tests for STLReader - Error Handling
# =============================================================================


class TestSTLReaderErrorHandling:
    """Tests for error handling in STLReader."""

    def test_empty_data_raises_error(self):
        """Empty data should raise ValueError."""
        reader = STLReader()

        with pytest.raises(ValueError, match="STL raw data in bytes is required"):
            reader.read(b"")

    def test_short_data_raises_error(self):
        """Data shorter than GSI block should raise ValueError."""
        reader = STLReader()

        with pytest.raises(ValueError, match="STL file too short"):
            reader.read(b"x" * 500)

    def test_invalid_stl_raises_error(self):
        """Invalid STL format should raise ValueError."""
        reader = STLReader()
        invalid_data = bytearray(1024)
        invalid_data[3:11] = b"INVALID!"  # Invalid DFC

        with pytest.raises(ValueError, match="Invalid EBU-STL file"):
            reader.read(bytes(invalid_data))


# =============================================================================
# Tests for STLReader - Properties are Read-Only
# =============================================================================


class TestSTLReaderProperties:
    """Tests for read-only properties."""

    def test_captions_property_returns_parsed_data(self):
        """captions property should return parsed captions."""
        reader = STLReader()
        stl_data = make_stl_file()

        reader.read(stl_data)

        assert reader.captions is not None
        assert isinstance(reader.captions, list)

    def test_gsi_property_returns_gsi_info(self):
        """gsi property should return GSI information."""
        reader = STLReader()
        stl_data = make_stl_file()

        reader.read(stl_data)

        assert reader.gsi is not None
        assert "disk_format_code" in reader.gsi
