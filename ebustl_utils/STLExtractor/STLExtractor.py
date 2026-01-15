import json
import os
import subprocess
import tempfile
from typing import Optional

from .helpers import convert_teletext_to_stl
from ebustl_utils.models import VideoInfo


class STLExtractor:
    """
    Extracts teletext data from MXF file and converts it to EBU STL format.

    Args:
        mxf_path: Path to the MXF file (required)
        output_dir: Directory to save the output STL file (required).
                    The STL filename is derived from the MXF filename.
    """

    def __init__(
        self, mxf_path: Optional[str] = None, output_dir: Optional[str] = None
    ):
        if mxf_path is None:
            raise ValueError("MXF path is required")
        elif not mxf_path.lower().endswith(".mxf"):
            raise ValueError("MXF path must end with .mxf")

        if output_dir is None:
            raise ValueError("Output directory is required")

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Derive STL filename from MXF filename
        mxf_basename = os.path.basename(mxf_path)
        stl_filename = os.path.splitext(mxf_basename)[0] + ".stl"

        self.mxf_path = mxf_path
        self.output_dir = output_dir
        self.output_path = os.path.join(output_dir, stl_filename)
        self._video_info = self._get_mxf_video_info()
        self._raw_data = self._extract_raw_payload_from_mxf()

    def _get_mxf_video_info(self) -> Optional[VideoInfo]:
        """
        Extract video timing information from MXF file using ffprobe.

        Returns:
            VideoInfo with duration, frame rate, and total frames
        """
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            self.mxf_path,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            data = json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            print(f"Warning: Could not get video info: {e}")
            return None

        # Find video stream
        video_stream = None
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                video_stream = stream
                break

        if not video_stream:
            print("Warning: No video stream found in MXF")
            return None

        # Get frame rate (could be "25/1" or "25.0")
        frame_rate_str = video_stream.get("r_frame_rate", "25/1")
        if "/" in frame_rate_str:
            num, den = frame_rate_str.split("/")
            frame_rate = float(num) / float(den)
        else:
            frame_rate = float(frame_rate_str)

        # Get duration
        duration = float(video_stream.get("duration", 0))
        if duration == 0:
            # Try format duration
            duration = float(data.get("format", {}).get("duration", 0))

        # Calculate total frames
        total_frames = int(duration * frame_rate)

        # Get start timecode if available
        start_tc = video_stream.get("tags", {}).get("timecode", "00:00:00:00")

        print(
            f"Video info: {duration:.2f}s, {frame_rate}fps, {total_frames} frames, start TC: {start_tc}"
        )

        return VideoInfo(
            duration_seconds=duration,
            frame_rate=frame_rate,
            total_frames=total_frames,
            start_timecode=start_tc,
        )

    def _extract_raw_payload_from_mxf(self) -> bytes:
        """
        Extracts the raw payload from a MXF file.\n
        -map 0:d (or 0:s) selects the data/subtitle stream\n
        -c copy tells ffmpeg NOT to decode it\n
        -f data tells ffmpeg to write raw bytes without a container header\n
        ffmpeg -i input.mxf -map 0:d:0 -c copy -f data raw_ancillary.bin

        Note: Need to check ffmpeg -i input.mxf first to see if the stream is labeled as data (d:0) or subtitle (s:0).
        """
        print(f"Extracting raw payload from MXF file: {self.mxf_path}")
        stream_type = None
        # check if the stream is labeled as data (d:0) or subtitle (s:0)
        # ffmpeg -i returns exit code 1 when no output specified, and writes to stderr
        result = subprocess.run(
            ["ffmpeg", "-i", self.mxf_path], capture_output=True, text=True
        )
        output = result.stderr  # ffmpeg writes info to stderr
        if "Data:" in output:
            stream_type = "d:0"
        elif "Subtitle:" in output:
            stream_type = "s:0"
        else:
            raise ValueError("No data/subtitle stream found in the MXF file")

        # create a temp file for the raw ancillary data
        temp_file = tempfile.NamedTemporaryFile(suffix=".bin", delete=False)
        temp_path = temp_file.name
        temp_file.close()

        try:
            subprocess.check_output(
                [
                    "ffmpeg",
                    "-y",  # overwrite output file without asking
                    "-i",
                    self.mxf_path,
                    "-map",
                    f"0:{stream_type}",
                    "-c",
                    "copy",
                    "-f",
                    "data",
                    temp_path,
                ],
                stderr=subprocess.STDOUT,
            )

            # read the raw data from the temp file
            with open(temp_path, "rb") as f:
                raw_data = f.read()
            return raw_data

        except subprocess.CalledProcessError as e:
            print(f"Error extracting raw payload from MXF file: {e}")
            raise e

        finally:
            # clean up the temp file
            if os.path.exists(temp_path):
                print(f"Removing temp file: {temp_path}")
                os.remove(temp_path)

    def _has_teletext_data(self) -> bool:
        """
        Check if raw data contains actual teletext/OP-47 packets.

        OP-47 teletext data contains sync patterns: 0x55 0x55 0x27
        (clock run-in + framing code)

        Returns:
            True if teletext sync patterns are found
        """
        # OP-47/VANC teletext sync pattern
        TELETEXT_SYNC = b"\x55\x55\x27"

        # Count sync patterns - need at least a few to be valid
        sync_count = self._raw_data.count(TELETEXT_SYNC)

        return sync_count >= 10  # At least 10 teletext packets to be considered valid

    def extract(self):
        """
        Convert MXF file with embedded teletext to EBU STL format.

        Extracts ALL teletext pages from the MXF file.

        Returns:
            Number of subtitles extracted

        Raises:
            ValueError: If file doesn't contain teletext/OP-47 subtitle data
        """
        # Get video timing info
        print(f"Extracting data stream from: {self.mxf_path}")

        if not self._raw_data:
            raise ValueError("No data extracted from MXF file")

        print(f"Extracted {len(self._raw_data)} bytes of data")

        # Verify the data actually contains teletext packets
        if not self._has_teletext_data():
            raise ValueError(
                f"MXF file {self.mxf_path} does not contain teletext/OP-47 subtitle data. "
                "The data stream exists but contains no teletext packets (no 0x55 0x55 0x27 sync patterns found)."
            )

        print("Verified: Data contains OP-47 teletext packets")

        # Convert to STL with video timing info
        count = convert_teletext_to_stl(
            self._raw_data,
            self.output_path,
            program_title=os.path.basename(self.mxf_path),
            total_frames=self._video_info.total_frames if self._video_info else None,
            frame_rate=self._video_info.frame_rate if self._video_info else 25,
        )

        print(f"Converted {count} subtitles to STL file: {self.output_path}")
