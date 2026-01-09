"""
STLReader - minimal EBU STL (.stl) binary reader.

Supports EBU TECH 3264‑E (EBU STL file) format.

The reader focuses on deterministic parsing of:
- GSI block (first 1024 bytes) for basic metadata and frame‑rate
- TTI blocks (128 bytes each) for timing and human‑readable text

It returns a caption list:
    [
        {
            "start": 0,                       # microseconds
            "start_timecode": "00:00:00;00",  # timecode format
            "end": 2500000,                   # microseconds
            "end_timecode": "00:00:02;12",    # timecode format
            "text": "Caption text",
            "style": {                        # CSS-like styling (None if not present)
                "color": "red",               # foreground color
                "background-color": "black",  # background color (boxing)
                "font-style": "italic",
                "font-weight": "bold",
                "text-decoration": "underline",
                "visibility": "flash",        # flashing text
                "line-height": "double",      # double-height text
            },
            "layout": {                       # positioning info (None if not present)
                "vertical_position": 20,      # row 0-23
                "text_align": "center",       # left, center, right
            },
        },
        ...
    ]
"""

from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ebustl_utils.stl_helpers import (
    EBUSTLControlCode,
    JustificationCode,
    TELETEXT_COLOR_NAMES,
)


@dataclass
class STLCaption:
    start: int  # microseconds
    end: int  # microseconds
    text: str
    start_timecode: str
    end_timecode: str
    # Style attributes
    color: Optional[str] = None
    background_color: Optional[str] = None
    italic: bool = False
    bold: bool = False
    underline: bool = False
    flash: bool = False
    double_height: bool = False
    # Layout attributes
    vertical_position: Optional[int] = None  # Row 0-23
    justification: Optional[str] = None  # left, center, right

    def to_dict(self) -> Dict[str, Any]:
        # Build style dict only if there are styling attributes
        style: Optional[Dict[str, Any]] = None
        has_style = (
            self.color
            or self.background_color
            or self.italic
            or self.bold
            or self.underline
            or self.flash
            or self.double_height
        )
        if has_style:
            style = {}
            if self.color:
                style["color"] = self.color
            if self.background_color:
                style["background-color"] = self.background_color
            if self.italic:
                style["font-style"] = "italic"
            if self.bold:
                style["font-weight"] = "bold"
            if self.underline:
                style["text-decoration"] = "underline"
            if self.flash:
                style["visibility"] = "flash"
            if self.double_height:
                style["line-height"] = "double"

        # Build layout dict only if there are positioning attributes
        layout: Optional[Dict[str, Any]] = None
        if self.vertical_position is not None or self.justification:
            layout = {}
            if self.vertical_position is not None:
                layout["vertical_position"] = self.vertical_position
            if self.justification:
                layout["text_align"] = self.justification

        return {
            "start": self.start,
            "start_timecode": self.start_timecode,
            "end": self.end,
            "end_timecode": self.end_timecode,
            "text": self.text,
            "style": style,
            "layout": layout,
        }


class STLReader:
    """
    Lightweight EBU STL binary reader focused on timing + text.

    This does NOT attempt to be a full Tech 3264‑E implementation; instead it
    implements a stable, deterministic subset that works for EBU TECH 3264‑E STL files.
    """

    def __init__(self, fps_override: Optional[float] = None):
        """
        Args:
            fps_override: Optional FPS to force for timecode conversion.
                          If None, we derive FPS from the GSI Disk Format Code.
        """

        self._fps_override = fps_override

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def read(self, raw: bytes) -> Dict[str, Any]:
        """
        Parse STL binary bytes and return a caption payload
        """
        if not raw:
            return {"captions": [], "fps": self._fps_override or 25.0, "gsi": {}}

        if len(raw) < 1024:
            raise ValueError(
                f"STL file too short to contain GSI header: {len(raw)} bytes"
            )

        buffer = io.BytesIO(raw)

        # GSI block (first 1024 bytes)
        gsi = buffer.read(1024)
        gsi_info, fps = self._parse_gsi(gsi)

        if self._fps_override:
            fps = self._fps_override

        # TTI blocks (remaining 128‑byte records)
        captions = self._parse_tti_blocks(buffer, fps)

        return {
            "captions": [c.to_dict() for c in captions],
            "fps": fps,
            "gsi": gsi_info,
        }

    # ------------------------------------------------------------------ #
    # GSI parsing
    # ------------------------------------------------------------------ #
    def _parse_gsi(self, gsi: bytes) -> Tuple[Dict[str, Any], float]:
        """
        Parse just enough of the GSI block to determine frame‑rate and
        expose a few commonly useful fields.

        Offsets are based on EBU Tech 3264‑E; we keep this intentionally
        conservative and defensive.
        """
        if len(gsi) != 1024:
            raise ValueError(f"GSI block must be 1024 bytes, got {len(gsi)}")

        def _safe_str(slice_: bytes) -> str:
            return slice_.decode("ascii", errors="ignore").strip()

        # Disk Format Code typically looks like "STL25.01", "STL30.01", etc.
        dfc = _safe_str(gsi[3:11])

        # Programme title (TPN) and original programme title (TPN2) are
        # optional but nice to have when debugging.
        tpn = _safe_str(gsi[16:48])  # Title
        tna = _safe_str(gsi[48:80])  # Programme name / episode

        # Character code table (CCT) defines encoding (Latin, Cyrillic, etc.).
        cct = _safe_str(gsi[12:16])

        fps = self._derive_fps_from_dfc(dfc)

        info: Dict[str, Any] = {
            "disk_format_code": dfc,
            "title": tpn,
            "programme_name": tna,
            "character_code_table": cct,
            "frame_rate": fps,
        }

        return info, fps

    @staticmethod
    def _derive_fps_from_dfc(dfc: str) -> float:
        """
        Infer frame‑rate from Disk Format Code (DFC).
        Common values: STL25.xx, STL30.xx, STL24.xx
        """
        dfc_upper = (dfc or "").upper()
        if "25" in dfc_upper:
            return 25.0
        if "30" in dfc_upper:
            return 30.0
        if "24" in dfc_upper:
            return 24.0
        # Fallback to PAL 25 fps, which is the most common for EBU STL
        return 25.0

    # ------------------------------------------------------------------ #
    # TTI parsing
    # ------------------------------------------------------------------ #
    def _parse_tti_blocks(self, buffer: io.BytesIO, fps: float) -> List[STLCaption]:
        """
        Parse all 128‑byte TTI blocks from the given buffer.

        We support multi‑block subtitles by accumulating text per Subtitle
        Number (SN) and flushing on CS == 0x00 (single) or 0x03 (last).
        """
        captions: List[STLCaption] = []
        pending_blocks: Dict[int, Dict[str, Any]] = {}

        def finalize_caption(sn: int) -> None:
            entry = pending_blocks.pop(sn, None)
            if not entry:
                return

            text_chunks = entry.get("text_chunks", [])
            full_text = "".join(text_chunks).strip()
            if not full_text:
                return

            start_seconds = entry.get("start_seconds", 0.0)
            end_seconds = entry.get("end_seconds", start_seconds)
            start_us = int(start_seconds * 1_000_000)  # Convert to microseconds
            end_us = int(end_seconds * 1_000_000)  # Convert to microseconds
            start_tc = self._format_timecode_from_seconds(start_seconds, fps)
            end_tc = self._format_timecode_from_seconds(end_seconds, fps)

            captions.append(
                STLCaption(
                    start=start_us,
                    end=end_us,
                    text=full_text,
                    start_timecode=start_tc,
                    end_timecode=end_tc,
                    color=entry.get("color"),
                    background_color=entry.get("background_color"),
                    italic=entry.get("italic", False),
                    bold=entry.get("bold", False),
                    underline=entry.get("underline", False),
                    flash=entry.get("flash", False),
                    double_height=entry.get("double_height", False),
                    vertical_position=entry.get("vertical_position"),
                    justification=entry.get("justification"),
                )
            )

        while True:
            tti = buffer.read(128)
            if not tti:
                break
            if len(tti) < 128:
                # Ignore trailing partial block – file may be truncated
                break

            # TTI layout (128 bytes) – key fields only:
            #  0:     SGN  (Subtitle Group Number)
            #  1‑2:   SN   (Subtitle Number, big‑endian)
            #  3:     EBN  (Extension Block Number)
            #  4:     CS   (Cumulative Status: 0=single,1=first,2=intermediate,3=last)
            #  5‑8:   TCI  (In‑cue   HH:MM:SS:FF, 1 byte per field)
            #  9‑12:  TCO  (Out‑cue  HH:MM:SS:FF, 1 byte per field)
            #  13:    VP   (Vertical Position, row 0-23)
            #  14:    JC   (Justification Code: 0=unchanged, 1=left, 2=center, 3=right)
            #  15:    CF   (Comment Flag: 0=subtitle, 1=comment)
            #  16‑127: Text field (112 bytes)
            sn = struct.unpack(">H", tti[1:3])[0]
            ebn = tti[3]
            cs = tti[4]
            vp = tti[13]  # Vertical Position (row 0-23)
            jc = tti[14]  # Justification Code

            # Only skip user data blocks (0xF0-0xFF).
            # EBU Tech 3264 assigns 0x00-0xEF for subtitle data.
            # However, some files use EBN=0xFF for valid captions.
            # We'll try to detect this by checking if the text field contains printable characters.
            if ebn >= 0xF0:
                # Heuristic: if the text field (bytes 16-128) has printable ASCII,
                # treat it as a valid caption block despite the high EBN.
                text_payload = tti[16:128]
                has_printable = any(32 <= b < 127 for b in text_payload)
                if not has_printable:
                    continue
            tci_h, tci_m, tci_s, tci_f = tti[5], tti[6], tti[7], tti[8]
            tco_h, tco_m, tco_s, tco_f = tti[9], tti[10], tti[11], tti[12]

            text_raw = tti[16:128]

            decoded = self._decode_ebu_stl_text(text_raw)
            text = decoded["text"]

            start_seconds = tci_h * 3600 + tci_m * 60 + tci_s + tci_f / fps
            end_seconds = tco_h * 3600 + tco_m * 60 + tco_s + tco_f / fps

            # Map justification code to alignment string
            justification: Optional[str] = None
            if jc == JustificationCode.LEFT:
                justification = "left"
            elif jc == JustificationCode.CENTERED:
                justification = "center"
            elif jc == JustificationCode.RIGHT:
                justification = "right"
            # JustificationCode.UNCHANGED (0x00) means no preference, keep None

            entry = pending_blocks.get(sn)
            if entry is None:
                entry = {
                    "text_chunks": [],
                    "color": decoded["color"],
                    "background_color": decoded["background_color"],
                    "italic": decoded["italic"],
                    "bold": decoded["bold"],
                    "underline": decoded["underline"],
                    "flash": decoded["flash"],
                    "double_height": decoded["double_height"],
                    "start_seconds": start_seconds,
                    "end_seconds": end_seconds,
                    "vertical_position": vp if vp <= 23 else None,
                    "justification": justification,
                }
                pending_blocks[sn] = entry
            else:
                entry["start_seconds"] = min(entry["start_seconds"], start_seconds)
                entry["end_seconds"] = max(entry["end_seconds"], end_seconds)
                # Merge style attributes (OR for booleans, keep first non-None for colors)
                entry["italic"] = entry["italic"] or decoded["italic"]
                entry["bold"] = entry["bold"] or decoded["bold"]
                entry["underline"] = entry["underline"] or decoded["underline"]
                entry["flash"] = entry["flash"] or decoded["flash"]
                entry["double_height"] = (
                    entry["double_height"] or decoded["double_height"]
                )
                if decoded["color"] and not entry["color"]:
                    entry["color"] = decoded["color"]
                if decoded["background_color"] and not entry["background_color"]:
                    entry["background_color"] = decoded["background_color"]
                # Keep first valid layout values
                if justification and not entry["justification"]:
                    entry["justification"] = justification

            if text:
                entry["text_chunks"].append(text)

            # Flush entry for single or last block
            if cs in (0x00, 0x03):
                finalize_caption(sn)

        # Flush any remaining pending captions
        for remaining_sn in list(pending_blocks.keys()):
            finalize_caption(remaining_sn)

        return captions

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _decode_ebu_stl_text(text_raw: bytes) -> Dict[str, Any]:
        """
        Decode the 112‑byte text field from a TTI block.

        Returns a dict with:
            - text: decoded text string
            - color: foreground color (or None if white/default)
            - background_color: background color from boxing (or None)
            - italic: bool
            - bold: bool
            - underline: bool
            - flash: bool
            - double_height: bool

        Uses EBUSTLControlCode enum from stl_helpers for control code values.
        """
        text_chars: List[str] = []
        italic = False
        bold = False
        underline = False
        flash = False
        double_height = False
        current_color = "white"
        background_color: Optional[str] = None

        for byte in text_raw:
            # Unused space filler
            if byte == EBUSTLControlCode.UNUSED_SPACE:
                continue
            # Foreground colors (0x00-0x07)
            if EBUSTLControlCode.ALPHA_BLACK <= byte <= EBUSTLControlCode.ALPHA_WHITE:
                current_color = TELETEXT_COLOR_NAMES.get(byte, current_color)
                continue
            # Flash ON
            if byte == EBUSTLControlCode.FLASH:
                flash = True
                continue
            # Flash OFF (steady)
            if byte == EBUSTLControlCode.STEADY:
                flash = False
                continue
            # End box - no action needed, boxing state tracked via background_color
            if byte == EBUSTLControlCode.END_BOX:
                continue
            # Start box - creates background
            if byte == EBUSTLControlCode.START_BOX:
                # Boxing typically uses black background
                if background_color is None:
                    background_color = "black"
                continue
            # Normal height
            if byte == EBUSTLControlCode.NORMAL_HEIGHT:
                double_height = False
                continue
            # Double height
            if byte == EBUSTLControlCode.DOUBLE_HEIGHT:
                double_height = True
                continue
            # Italic ON
            if byte == EBUSTLControlCode.ITALIC_ON:
                italic = True
                continue
            # Italic OFF
            if byte == EBUSTLControlCode.ITALIC_OFF:
                italic = False
                continue
            # Underline ON
            if byte == EBUSTLControlCode.UNDERLINE_ON:
                underline = True
                continue
            # Underline OFF
            if byte == EBUSTLControlCode.UNDERLINE_OFF:
                underline = False
                continue
            # Boxing ON (some implementations use for bold)
            if byte == EBUSTLControlCode.BOXING_ON:
                bold = True
                continue
            # Boxing OFF
            if byte == EBUSTLControlCode.BOXING_OFF:
                bold = False
                continue
            # New line
            if byte == EBUSTLControlCode.NEWLINE:
                # Collapse consecutive newlines to match subtitle rendering behavior
                if not text_chars or text_chars[-1] != "\n":
                    text_chars.append("\n")
                continue

            # Printable range – EBU STL uses ISO 6937 or Latin‑1; we
            # approximate with ISO‑8859‑1, which is fine for QC‑style tools.
            if 32 <= byte < 127:
                text_chars.append(chr(byte))
            elif 128 <= byte <= 255:
                try:
                    text_chars.append(bytes([byte]).decode("latin-1"))
                except (UnicodeDecodeError, ValueError):
                    # Best‑effort: skip unknown bytes
                    continue

        return {
            "text": "".join(text_chars),
            "color": current_color if current_color != "white" else None,
            "background_color": background_color,
            "italic": italic,
            "bold": bold,
            "underline": underline,
            "flash": flash,
            "double_height": double_height,
        }

    @staticmethod
    def _format_timecode_from_seconds(seconds: float, fps: float) -> str:
        """
        Format seconds into HH:MM:SS;FF using the given frame‑rate.
        """
        if seconds < 0:
            seconds = 0.0

        total_frames = int(round(seconds * fps))
        s, f = divmod(total_frames, int(fps))
        h, rem = divmod(s, 3600)
        m, s = divmod(rem, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d};{int(f):02d}"
