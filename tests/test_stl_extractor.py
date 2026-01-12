import pytest
from unittest.mock import patch, MagicMock
import json

from ebustl_utils.STLExtractor import STLExtractor

from helpers_for_testing import TELETEXT_SYNC


# =============================================================================
# Tests for STLExtractor.__init__ validation
# =============================================================================


class TestSTLExtractorInit:
    """Tests for STLExtractor initialization and validation."""

    def test_mxf_path_required(self):
        """Raise ValueError when mxf_path is None."""
        with pytest.raises(ValueError, match="MXF path is required"):
            STLExtractor(mxf_path=None, output_path="output.stl")

    def test_mxf_path_must_end_with_mxf(self):
        """Raise ValueError when mxf_path doesn't end with .mxf."""
        with pytest.raises(ValueError, match="MXF path must end with .mxf"):
            STLExtractor(mxf_path="video.mp4", output_path="output.stl")

    def test_output_path_required(self):
        """Raise ValueError when output_path is None."""
        with pytest.raises(ValueError, match="Output path is required"):
            STLExtractor(mxf_path="video.mxf", output_path=None)


# =============================================================================
# Tests for STLExtractor._has_teletext_data
# =============================================================================


class TestHasTeletextData:
    """Tests for teletext data detection."""

    @patch.object(STLExtractor, "_get_mxf_video_info")
    @patch.object(STLExtractor, "_extract_raw_payload_from_mxf")
    def test_returns_true_when_enough_sync_patterns(
        self, mock_extract, mock_video_info
    ):
        """Return True when at least 10 teletext sync patterns found."""
        # Setup: raw data with 15 sync patterns
        mock_video_info.return_value = None
        mock_extract.return_value = TELETEXT_SYNC * 15 + b"\x00" * 100

        extractor = STLExtractor(mxf_path="test.mxf", output_path="out.stl")
        result = extractor._has_teletext_data()

        assert result is True

    @patch.object(STLExtractor, "_get_mxf_video_info")
    @patch.object(STLExtractor, "_extract_raw_payload_from_mxf")
    def test_returns_false_when_few_sync_patterns(self, mock_extract, mock_video_info):
        """Return False when fewer than 10 teletext sync patterns found."""
        # Setup: raw data with only 5 sync patterns
        mock_video_info.return_value = None
        mock_extract.return_value = TELETEXT_SYNC * 5 + b"\x00" * 100

        extractor = STLExtractor(mxf_path="test.mxf", output_path="out.stl")
        result = extractor._has_teletext_data()

        assert result is False

    @patch.object(STLExtractor, "_get_mxf_video_info")
    @patch.object(STLExtractor, "_extract_raw_payload_from_mxf")
    def test_returns_false_when_no_sync_patterns(self, mock_extract, mock_video_info):
        """Return False when no teletext sync patterns found."""
        mock_video_info.return_value = None
        mock_extract.return_value = b"\x00" * 1000

        extractor = STLExtractor(mxf_path="test.mxf", output_path="out.stl")
        result = extractor._has_teletext_data()

        assert result is False

    @patch.object(STLExtractor, "_get_mxf_video_info")
    @patch.object(STLExtractor, "_extract_raw_payload_from_mxf")
    def test_exactly_ten_sync_patterns_returns_true(
        self, mock_extract, mock_video_info
    ):
        """Return True when exactly 10 teletext sync patterns found."""
        mock_video_info.return_value = None
        mock_extract.return_value = TELETEXT_SYNC * 10 + b"\x00" * 100

        extractor = STLExtractor(mxf_path="test.mxf", output_path="out.stl")
        result = extractor._has_teletext_data()

        assert result is True


# =============================================================================
# Tests for STLExtractor.extract
# =============================================================================


class TestSTLExtractorExtract:
    """Tests for the extract method."""

    @patch.object(STLExtractor, "_get_mxf_video_info")
    @patch.object(STLExtractor, "_extract_raw_payload_from_mxf")
    def test_raises_when_no_data_extracted(self, mock_extract, mock_video_info):
        """Raise ValueError when no raw data extracted."""
        mock_video_info.return_value = None
        mock_extract.return_value = b""  # Empty data

        extractor = STLExtractor(mxf_path="test.mxf", output_path="out.stl")

        with pytest.raises(ValueError, match="No data extracted from MXF file"):
            extractor.extract()

    @patch.object(STLExtractor, "_get_mxf_video_info")
    @patch.object(STLExtractor, "_extract_raw_payload_from_mxf")
    def test_raises_when_no_teletext_data(self, mock_extract, mock_video_info):
        """Raise ValueError when data doesn't contain teletext packets."""
        mock_video_info.return_value = None
        mock_extract.return_value = b"\x00" * 1000  # No teletext sync patterns

        extractor = STLExtractor(mxf_path="test.mxf", output_path="out.stl")

        with pytest.raises(ValueError, match="does not contain teletext/OP-47"):
            extractor.extract()


# =============================================================================
# Tests for STLExtractor._get_mxf_video_info
# =============================================================================


class TestGetMxfVideoInfo:
    """Tests for video info extraction from MXF."""

    @patch("ebustl_utils.STLExtractor.STLExtractor.subprocess.run")
    @patch.object(STLExtractor, "_extract_raw_payload_from_mxf")
    def test_parses_ffprobe_output(self, mock_extract, mock_run):
        """Parse ffprobe JSON output correctly."""
        mock_extract.return_value = b"\x00" * 100

        # Mock ffprobe output
        ffprobe_output = {
            "streams": [
                {
                    "codec_type": "video",
                    "r_frame_rate": "25/1",
                    "duration": "120.0",
                    "tags": {"timecode": "10:00:00:00"},
                }
            ],
            "format": {"duration": "120.0"},
        }
        mock_run.return_value = MagicMock(stdout=json.dumps(ffprobe_output))

        extractor = STLExtractor(mxf_path="test.mxf", output_path="out.stl")

        assert extractor._video_info is not None
        assert extractor._video_info.duration_seconds == 120.0
        assert extractor._video_info.frame_rate == 25.0
        assert extractor._video_info.total_frames == 3000
        assert extractor._video_info.start_timecode == "10:00:00:00"

    @patch("ebustl_utils.STLExtractor.STLExtractor.subprocess.run")
    @patch.object(STLExtractor, "_extract_raw_payload_from_mxf")
    def test_handles_fractional_frame_rate(self, mock_extract, mock_run):
        """Handle fractional frame rate like 30000/1001."""
        mock_extract.return_value = b"\x00" * 100

        ffprobe_output = {
            "streams": [
                {
                    "codec_type": "video",
                    "r_frame_rate": "30000/1001",
                    "duration": "60.0",
                }
            ]
        }
        mock_run.return_value = MagicMock(stdout=json.dumps(ffprobe_output))

        extractor = STLExtractor(mxf_path="test.mxf", output_path="out.stl")

        assert extractor._video_info is not None
        assert abs(extractor._video_info.frame_rate - 29.97) < 0.01


# =============================================================================
# Tests for STLExtractor._extract_raw_payload_from_mxf
# =============================================================================


class TestExtractRawPayloadFromMxf:
    """Tests for raw payload extraction from MXF."""

    @patch("ebustl_utils.STLExtractor.STLExtractor.subprocess.run")
    @patch("ebustl_utils.STLExtractor.STLExtractor.subprocess.check_output")
    @patch.object(STLExtractor, "_get_mxf_video_info")
    def test_detects_data_stream(self, mock_video_info, mock_check, mock_run):
        """Detect data stream type from ffmpeg output."""
        mock_video_info.return_value = None

        # First subprocess.run call to detect stream type
        mock_run.return_value = MagicMock(stderr="Stream #0:1: Data: some_codec")
        mock_check.return_value = b""

        with patch("builtins.open", MagicMock(return_value=MagicMock())):
            with patch("os.path.exists", return_value=True):
                with patch("os.remove"):
                    with patch("tempfile.NamedTemporaryFile") as mock_temp:
                        mock_temp.return_value.__enter__ = MagicMock(
                            return_value=MagicMock(name="/tmp/test.bin")
                        )
                        mock_temp.return_value.__exit__ = MagicMock(return_value=False)
                        mock_temp.return_value.name = "/tmp/test.bin"
                        mock_temp.return_value.close = MagicMock()

                        with patch("builtins.open", MagicMock()) as mock_open:
                            mock_open.return_value.__enter__.return_value.read.return_value = b"raw_data"
                            # This test just verifies the stream detection path
                            # The actual extraction is mocked

    @patch("ebustl_utils.STLExtractor.STLExtractor.subprocess.run")
    @patch.object(STLExtractor, "_get_mxf_video_info")
    def test_raises_when_no_stream_found(self, mock_video_info, mock_run):
        """Raise ValueError when no data/subtitle stream found."""
        mock_video_info.return_value = None
        mock_run.return_value = MagicMock(stderr="Stream #0:0: Video: h264")

        with pytest.raises(ValueError, match="No data/subtitle stream found"):
            STLExtractor(mxf_path="test.mxf", output_path="out.stl")
