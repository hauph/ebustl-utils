import warnings

import pytest
from ebustl_utils.STLReader.decoder import decode_stl_file
from ebustl_utils.STLReader.STLValidationWarning import STLValidationWarning

from helpers_for_testing import make_gsi_block, make_stl_file, make_tti_block


# =============================================================================
# Tests for decode_stl_file - Input Validation
# =============================================================================


class TestDecodeStlFileValidation:
    """Tests for input validation in decode_stl_file."""

    def test_empty_input_raises_error(self):
        """Empty bytes should raise ValueError."""
        with pytest.raises(ValueError, match="STL raw data in bytes is required"):
            decode_stl_file(b"", fps_override=None)

    def test_none_input_raises_error(self):
        """None input should raise ValueError."""
        with pytest.raises(ValueError, match="STL raw data in bytes is required"):
            decode_stl_file(None, fps_override=None)

    def test_file_too_short_raises_error(self):
        """Files shorter than 1024 bytes should raise ValueError."""
        short_data = b"x" * 500

        with pytest.raises(ValueError, match="STL file too short"):
            decode_stl_file(short_data, fps_override=None)

    def test_invalid_dfc_raises_error(self):
        """Invalid Disk Format Code should raise ValueError."""
        # Create 1024 bytes with invalid DFC (not starting with "STL")
        invalid_gsi = bytearray(1024)
        invalid_gsi[3:11] = b"INVALID!"  # Invalid DFC

        with pytest.raises(ValueError, match="Invalid EBU-STL file"):
            decode_stl_file(bytes(invalid_gsi), fps_override=None)

    def test_valid_dfc_stl25(self):
        """STL25.01 should be recognized as valid."""
        stl_data = make_stl_file()

        result = decode_stl_file(stl_data, fps_override=None)

        assert result is not None
        assert result["fps"] == 25.0

    def test_valid_dfc_stl30(self):
        """STL30.01 should be recognized as valid."""
        gsi = make_gsi_block(dfc=b"STL30.01")
        stl_data = make_stl_file(gsi=gsi)

        result = decode_stl_file(stl_data, fps_override=None)

        assert result["fps"] == 30.0

    def test_valid_dfc_stl24(self):
        """STL24.01 should be recognized as valid."""
        gsi = make_gsi_block(dfc=b"STL24.01")
        stl_data = make_stl_file(gsi=gsi)

        result = decode_stl_file(stl_data, fps_override=None)

        assert result["fps"] == 24.0


# =============================================================================
# Tests for decode_stl_file - FPS Override
# =============================================================================


class TestDecodeStlFileFpsOverride:
    """Tests for FPS override functionality."""

    def test_fps_override_applied(self):
        """FPS override should replace detected fps."""
        stl_data = make_stl_file()  # Default is STL25.01

        result = decode_stl_file(stl_data, fps_override=29.97)

        assert result["fps"] == 29.97

    def test_fps_override_none_uses_detected(self):
        """None fps_override should use detected fps from DFC."""
        gsi = make_gsi_block(dfc=b"STL30.01")
        stl_data = make_stl_file(gsi=gsi)

        result = decode_stl_file(stl_data, fps_override=None)

        assert result["fps"] == 30.0


# =============================================================================
# Tests for decode_stl_file - GSI Parsing
# =============================================================================


class TestDecodeStlFileGsiParsing:
    """Tests for GSI block parsing."""

    def test_gsi_info_returned(self):
        """GSI information should be included in result."""
        stl_data = make_stl_file()

        result = decode_stl_file(stl_data, fps_override=None)

        assert "gsi" in result
        assert isinstance(result["gsi"], dict)

    def test_gsi_disk_format_code(self):
        """GSI should contain disk format code."""
        gsi = make_gsi_block(dfc=b"STL25.01")
        stl_data = make_stl_file(gsi=gsi)

        result = decode_stl_file(stl_data, fps_override=None)

        assert result["gsi"]["disk_format_code"] == "STL25.01"

    def test_gsi_character_code_table(self):
        """GSI should contain character code table."""
        gsi = make_gsi_block(cct=b"00")
        stl_data = make_stl_file(gsi=gsi)

        result = decode_stl_file(stl_data, fps_override=None)

        assert result["gsi"]["character_code_table"] == "00"


# =============================================================================
# Tests for decode_stl_file - TTI/Caption Parsing
# =============================================================================


class TestDecodeStlFileCaptionParsing:
    """Tests for TTI block parsing and caption extraction."""

    def test_captions_returned_as_list(self):
        """Captions should be returned as a list of dicts."""
        stl_data = make_stl_file()

        result = decode_stl_file(stl_data, fps_override=None)

        assert "captions" in result
        assert isinstance(result["captions"], list)

    def test_single_caption_parsed(self):
        """Single TTI block should produce one caption."""
        tti = make_tti_block(text=b"Test caption")
        stl_data = make_stl_file(tti_blocks=[tti])

        result = decode_stl_file(stl_data, fps_override=None)

        assert len(result["captions"]) == 1
        assert "Test caption" in result["captions"][0]["text"]

    def test_multiple_captions_parsed(self):
        """Multiple TTI blocks should produce multiple captions."""
        tti1 = make_tti_block(sn=1, text=b"Caption one")
        tti2 = make_tti_block(sn=2, text=b"Caption two")
        stl_data = make_stl_file(tti_blocks=[tti1, tti2])

        result = decode_stl_file(stl_data, fps_override=None)

        assert len(result["captions"]) == 2

    def test_caption_has_timing_fields(self):
        """Captions should have start/end timing fields."""
        tti = make_tti_block(
            tci=(0, 0, 1, 0),  # 00:00:01:00
            tco=(0, 0, 3, 12),  # 00:00:03:12
        )
        stl_data = make_stl_file(tti_blocks=[tti])

        result = decode_stl_file(stl_data, fps_override=None)
        caption = result["captions"][0]

        assert "start" in caption
        assert "end" in caption
        assert "start_timecode" in caption
        assert "end_timecode" in caption

    def test_caption_timing_values(self):
        """Caption timing should be correctly calculated."""
        # At 25fps: 00:00:01:00 = 1 second = 1,000,000 microseconds
        tti = make_tti_block(
            tci=(0, 0, 1, 0),  # 1 second
            tco=(0, 0, 2, 0),  # 2 seconds
        )
        stl_data = make_stl_file(tti_blocks=[tti])

        result = decode_stl_file(stl_data, fps_override=None)
        caption = result["captions"][0]

        assert caption["start"] == 1_000_000  # 1 second in microseconds
        assert caption["end"] == 2_000_000  # 2 seconds in microseconds

    def test_empty_tti_block_not_included(self):
        """TTI blocks with no text should not produce captions."""
        # Create a TTI block with empty/whitespace text
        tti_empty = make_tti_block(text=b"   ")
        tti_valid = make_tti_block(sn=2, text=b"Valid caption")
        stl_data = make_stl_file(tti_blocks=[tti_empty, tti_valid])

        result = decode_stl_file(stl_data, fps_override=None)

        # Only the valid caption should be present
        assert len(result["captions"]) == 1
        assert "Valid caption" in result["captions"][0]["text"]


# =============================================================================
# Tests for decode_stl_file - Return Structure
# =============================================================================


class TestDecodeStlFileReturnStructure:
    """Tests for the overall return structure."""

    def test_return_structure_has_required_keys(self):
        """Return dict should have captions, fps, and gsi keys."""
        stl_data = make_stl_file()

        result = decode_stl_file(stl_data, fps_override=None)

        assert "captions" in result
        assert "fps" in result
        assert "gsi" in result

    def test_captions_are_serialized_dicts(self):
        """Captions should be serialized as dicts (via to_dict)."""
        tti = make_tti_block(text=b"Test")
        stl_data = make_stl_file(tti_blocks=[tti])

        result = decode_stl_file(stl_data, fps_override=None)

        # Should be dict, not STLCaption object
        assert isinstance(result["captions"][0], dict)
        assert "text" in result["captions"][0]


# =============================================================================
# Tests for decode_stl_file - Validation Warnings
# =============================================================================


class TestDecodeStlFileValidationWarnings:
    """Tests for EBN/CS validation warnings (Adobe Premiere compatibility)."""

    def test_no_warning_for_valid_single_blocks(self):
        """EBN=255 with CS=0 should not trigger warning (standard single block)."""
        tti = make_tti_block(sn=1, ebn=0xFF, cs=0, text=b"Test")
        stl_data = make_stl_file(tti_blocks=[tti])

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            decode_stl_file(stl_data, fps_override=None)

            # No STLValidationWarning should be raised
            stl_warnings = [
                x for x in w if issubclass(x.category, STLValidationWarning)
            ]
            assert len(stl_warnings) == 0

    def test_no_warning_for_ebn_zero_with_cs_zero(self):
        """EBN=0 with CS=0 should not trigger warning (tolerated by Adobe)."""
        # EBN=0 is first block of extension, but CS=0 is tolerated
        tti1 = make_tti_block(sn=1, ebn=0, cs=0, text=b"First")
        tti2 = make_tti_block(sn=1, ebn=0xFF, cs=0, text=b"Last")
        stl_data = make_stl_file(tti_blocks=[tti1, tti2])

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            decode_stl_file(stl_data, fps_override=None)

            stl_warnings = [
                x for x in w if issubclass(x.category, STLValidationWarning)
            ]
            assert len(stl_warnings) == 0

    def test_warning_for_intermediate_ebn_with_cs_zero(self):
        """EBN=1,2,3... (intermediate) with CS=0 should trigger warning."""
        # This is invalid according to EBU spec and rejected by Adobe Premiere
        tti1 = make_tti_block(sn=1, ebn=0, cs=0, text=b"First")
        tti2 = make_tti_block(sn=1, ebn=1, cs=0, text=b"Intermediate")  # Invalid!
        tti3 = make_tti_block(sn=1, ebn=0xFF, cs=0, text=b"Last")
        stl_data = make_stl_file(tti_blocks=[tti1, tti2, tti3])

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            decode_stl_file(stl_data, fps_override=None)

            stl_warnings = [
                x for x in w if issubclass(x.category, STLValidationWarning)
            ]
            assert len(stl_warnings) == 1
            assert "intermediate EBN" in str(stl_warnings[0].message)

    def test_warning_for_multiple_intermediate_ebn_blocks(self):
        """Multiple intermediate EBN blocks with CS=0 should all be counted."""
        # Simulating basic_test.stl pattern that fails in Adobe
        tti_blocks = [
            make_tti_block(sn=1, ebn=0, cs=0, text=b"Block 0"),
            make_tti_block(sn=1, ebn=1, cs=0, text=b"Block 1"),  # Invalid
            make_tti_block(sn=1, ebn=2, cs=0, text=b"Block 2"),  # Invalid
            make_tti_block(sn=1, ebn=3, cs=0, text=b"Block 3"),  # Invalid
            make_tti_block(sn=1, ebn=0xFF, cs=0, text=b"Block last"),
        ]
        stl_data = make_stl_file(tti_blocks=tti_blocks)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            decode_stl_file(stl_data, fps_override=None)

            stl_warnings = [
                x for x in w if issubclass(x.category, STLValidationWarning)
            ]
            assert len(stl_warnings) == 1
            # Should report 3 blocks (EBN=1,2,3)
            assert "3 of first" in str(stl_warnings[0].message)

    def test_warning_only_checks_first_10_blocks(self):
        """Validation should only check first 10 TTI blocks."""
        # Create 15 blocks, with invalid blocks only at positions 11-14
        valid_blocks = [
            make_tti_block(sn=i, ebn=0xFF, cs=0, text=f"Valid {i}".encode())
            for i in range(10)
        ]
        # These invalid blocks are after the first 10, should not trigger warning
        invalid_blocks = [
            make_tti_block(sn=10 + i, ebn=1, cs=0, text=f"Invalid {i}".encode())
            for i in range(5)
        ]
        stl_data = make_stl_file(tti_blocks=valid_blocks + invalid_blocks)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            decode_stl_file(stl_data, fps_override=None)

            stl_warnings = [
                x for x in w if issubclass(x.category, STLValidationWarning)
            ]
            assert len(stl_warnings) == 0

    def test_valid_multi_block_extension_no_warning(self):
        """Valid multi-block extension with proper CS values should not warn."""
        # Proper multi-block: EBN=0 CS=1 (first), EBN=255 CS=3 (last)
        # Note: Our validation currently only checks EBN with CS=0, so this should pass
        tti1 = make_tti_block(sn=1, ebn=0, cs=1, text=b"First")
        tti2 = make_tti_block(sn=1, ebn=0xFF, cs=3, text=b"Last")
        stl_data = make_stl_file(tti_blocks=[tti1, tti2])

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            decode_stl_file(stl_data, fps_override=None)

            stl_warnings = [
                x for x in w if issubclass(x.category, STLValidationWarning)
            ]
            assert len(stl_warnings) == 0
