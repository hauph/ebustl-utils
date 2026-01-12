import pytest
from ebustl_utils.STLReader.parsers.gsi_parser import (
    decode_language_code,
    derive_fps_from_dfc,
    parse_gsi,
)
from helpers_for_testing import make_gsi_block


# =============================================================================
# Tests for decode_language_code
# =============================================================================


class TestDecodeLanguageCode:
    """Tests for EBU language code decoding."""

    def test_decode_english_code(self):
        """Should decode 0x09 as English (en)."""
        result = decode_language_code(b"09")
        assert result == "en"

    def test_decode_french_code(self):
        """Should decode 0x0F as French (fr)."""
        result = decode_language_code(b"0F")
        assert result == "fr"

    def test_decode_german_code(self):
        """Should decode 0x08 as German (de)."""
        result = decode_language_code(b"08")
        assert result == "de"

    def test_decode_spanish_code(self):
        """Should decode 0x0A as Spanish (es)."""
        result = decode_language_code(b"0A")
        assert result == "es"

    def test_decode_unknown_code_returns_empty(self):
        """Should return empty string for unknown code 0x00."""
        result = decode_language_code(b"00")
        assert result == ""

    def test_decode_empty_bytes_returns_none(self):
        """Should return None for empty bytes."""
        result = decode_language_code(b"")
        assert result is None

    def test_decode_whitespace_only_returns_none(self):
        """Should return None for whitespace-only bytes."""
        result = decode_language_code(b"  ")
        assert result is None

    def test_decode_invalid_hex_returns_none(self):
        """Should return None for invalid hex string."""
        result = decode_language_code(b"ZZ")
        assert result is None

    def test_decode_lowercase_hex(self):
        """Should handle lowercase hex values."""
        result = decode_language_code(b"0f")
        assert result == "fr"


# =============================================================================
# Tests for derive_fps_from_dfc
# =============================================================================


class TestDeriveFpsFromDfc:
    """Tests for frame rate derivation from Disk Format Code."""

    def test_stl25_returns_25fps(self):
        """Should return 25.0 fps for STL25.01."""
        result = derive_fps_from_dfc("STL25.01")
        assert result == 25.0

    def test_stl30_returns_30fps(self):
        """Should return 30.0 fps for STL30.01."""
        result = derive_fps_from_dfc("STL30.01")
        assert result == 30.0

    def test_stl24_returns_24fps(self):
        """Should return 24.0 fps for STL24.01."""
        result = derive_fps_from_dfc("STL24.01")
        assert result == 24.0

    def test_lowercase_dfc(self):
        """Should handle lowercase DFC strings."""
        result = derive_fps_from_dfc("stl25.01")
        assert result == 25.0

    def test_empty_string_returns_default_25fps(self):
        """Should return default 25.0 fps for empty string."""
        result = derive_fps_from_dfc("")
        assert result == 25.0

    def test_none_returns_default_25fps(self):
        """Should return default 25.0 fps for None."""
        result = derive_fps_from_dfc(None)
        assert result == 25.0

    def test_unknown_format_returns_default_25fps(self):
        """Should return default 25.0 fps for unknown format."""
        result = derive_fps_from_dfc("UNKNOWN")
        assert result == 25.0

    def test_partial_match_25(self):
        """Should match '25' anywhere in the string."""
        result = derive_fps_from_dfc("XYZ25ABC")
        assert result == 25.0


# =============================================================================
# Tests for parse_gsi
# =============================================================================


class TestParseGsi:
    """Tests for GSI block parsing."""

    def test_parse_valid_gsi_returns_tuple(self):
        """Should return tuple of (info_dict, fps)."""
        gsi = make_gsi_block()
        info, fps = parse_gsi(gsi)

        assert isinstance(info, dict)
        assert isinstance(fps, float)

    def test_parse_extracts_disk_format_code(self):
        """Should extract disk format code."""
        gsi = make_gsi_block(dfc=b"STL30.01")
        info, _ = parse_gsi(gsi)

        assert info["disk_format_code"] == "STL30.01"

    def test_parse_extracts_title(self):
        """Should extract title (TPN)."""
        gsi = make_gsi_block(title=b"My Test Title")
        info, _ = parse_gsi(gsi)

        assert info["title"] == "My Test Title"

    def test_parse_extracts_programme_name(self):
        """Should extract programme name (TNA)."""
        gsi = make_gsi_block(programme_name=b"Episode One")
        info, _ = parse_gsi(gsi)

        assert info["programme_name"] == "Episode One"

    def test_parse_extracts_character_code_table(self):
        """Should extract character code table (CCT)."""
        gsi = make_gsi_block(cct=b"01")
        info, _ = parse_gsi(gsi)

        assert info["character_code_table"] == "01"

    def test_parse_extracts_language(self):
        """Should decode and extract language code."""
        gsi = make_gsi_block(language_code=b"0F")  # French
        info, _ = parse_gsi(gsi)

        assert info["language"] == "fr"

    def test_parse_returns_correct_fps_25(self):
        """Should return 25.0 fps for STL25."""
        gsi = make_gsi_block(dfc=b"STL25.01")
        _, fps = parse_gsi(gsi)

        assert fps == 25.0

    def test_parse_returns_correct_fps_30(self):
        """Should return 30.0 fps for STL30."""
        gsi = make_gsi_block(dfc=b"STL30.01")
        _, fps = parse_gsi(gsi)

        assert fps == 30.0

    def test_parse_frame_rate_in_info_dict(self):
        """Should include frame_rate in info dict."""
        gsi = make_gsi_block(dfc=b"STL25.01")
        info, _ = parse_gsi(gsi)

        assert info["frame_rate"] == 25.0

    def test_parse_invalid_language_code_returns_none(self):
        """Should return None for invalid language code."""
        gsi = make_gsi_block(language_code=b"ZZ")
        info, _ = parse_gsi(gsi)

        assert info["language"] is None

    def test_parse_raises_for_wrong_size(self):
        """Should raise ValueError if GSI is not 1024 bytes."""
        with pytest.raises(ValueError, match="GSI block must be 1024 bytes"):
            parse_gsi(b"too short")

    def test_parse_raises_for_empty_bytes(self):
        """Should raise ValueError for empty bytes."""
        with pytest.raises(ValueError, match="GSI block must be 1024 bytes"):
            parse_gsi(b"")

    def test_parse_handles_all_spaces(self):
        """Should handle GSI block with all spaces (empty fields)."""
        gsi = b" " * 1024
        info, fps = parse_gsi(gsi)

        assert info["disk_format_code"] == ""
        assert info["title"] == ""
        assert fps == 25.0  # Default fallback
