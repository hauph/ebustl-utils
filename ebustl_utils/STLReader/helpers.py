"""
EBU STL Helpers - STLReader
- Reads .stl file and provides STL caption data structures with formatting:
    This module provides STL caption data structures with formatting.
    - Colors (text color/background color)
    - Layout (vertical position, justification)
    - Formatting (italic, bold, underline, double height, flash)
    - Font (font weight, font style)
"""

from typing import List, Dict, Optional, Any


from ebustl_utils.models import (
    EBUSTLControlCode,
    STLStyledSegment,
    TELETEXT_COLOR_NAMES,
    CCT_CODECS,
)


# Style fields to compare when merging segments (excludes 'text')
_STYLE_FIELDS = (
    "color",
    "background_color",
    "italic",
    "bold",
    "underline",
    "flash",
    "double_height",
)


def _segments_have_same_style(seg1: STLStyledSegment, seg2: STLStyledSegment) -> bool:
    """Check if two segments have identical style attributes."""
    return all(getattr(seg1, f) == getattr(seg2, f) for f in _STYLE_FIELDS)


def format_timecode_from_seconds(seconds: float, fps: float) -> str:
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


# =============================================================================
# STL Text Decoding Functions
# =============================================================================


def decode_ebu_stl_text(text_raw: bytes, cct: str = "00") -> Dict[str, Any]:
    """
    Decode the 112‑byte text field from a TTI block.

    Args:
        text_raw: Raw 112-byte text field from TTI block
        cct: Character Code Table from GSI (00=Latin, 01=Cyrillic, etc.)

    Returns a dict with:
        - text: decoded text string
        - color: foreground color (or None if white/default)
        - background_color: background color from boxing (or None)
        - italic: bool
        - bold: bool
        - underline: bool
        - flash: bool
        - double_height: bool
        - segments: list of STLStyledSegment for inline styled text
    """
    codec = CCT_CODECS.get(cct, "latin-1")

    # Current style state
    italic = False
    bold = False
    underline = False
    flash = False
    double_height = False
    current_color = "white"
    background_color: Optional[str] = None

    # Track styled segments for inline styling
    segments: List[STLStyledSegment] = []
    current_segment_text: List[str] = []

    def flush_segment():
        """Flush current text to a segment with current style."""
        nonlocal current_segment_text
        text = "".join(current_segment_text)
        if text:
            segments.append(
                STLStyledSegment(
                    text=text,
                    color=current_color if current_color != "white" else None,
                    background_color=background_color,
                    italic=italic,
                    bold=bold,
                    underline=underline,
                    flash=flash,
                    double_height=double_height,
                )
            )
        current_segment_text = []

    for byte in text_raw:
        # Unused space filler
        if byte == EBUSTLControlCode.UNUSED_SPACE:
            continue
        # Foreground colors (0x00-0x07)
        # These are "spacing attributes" in teletext - they occupy a character cell
        # position that displays as a space. Add space if there was preceding text.
        if EBUSTLControlCode.ALPHA_BLACK <= byte <= EBUSTLControlCode.ALPHA_WHITE:
            new_color = TELETEXT_COLOR_NAMES.get(byte, current_color)
            if new_color != current_color:
                # Add space for the control code position if there was preceding text
                if current_segment_text and not current_segment_text[-1].endswith(' '):
                    current_segment_text.append(' ')
                flush_segment()
                current_color = new_color
            continue
        # Flash ON
        if byte == EBUSTLControlCode.FLASH:
            if not flash:
                flush_segment()
                flash = True
            continue
        # Flash OFF (steady)
        if byte == EBUSTLControlCode.STEADY:
            if flash:
                flush_segment()
                flash = False
            continue
        # End box - no action needed, boxing state tracked via background_color
        if byte == EBUSTLControlCode.END_BOX:
            continue
        # Start box - creates background
        if byte == EBUSTLControlCode.START_BOX:
            # Boxing typically uses black background
            if background_color is None:
                flush_segment()
                background_color = "black"
            continue
        # Normal height
        if byte == EBUSTLControlCode.NORMAL_HEIGHT:
            if double_height:
                flush_segment()
                double_height = False
            continue
        # Double height
        if byte == EBUSTLControlCode.DOUBLE_HEIGHT:
            if not double_height:
                flush_segment()
                double_height = True
            continue
        # Italic ON
        if byte == EBUSTLControlCode.ITALIC_ON:
            if not italic:
                flush_segment()
                italic = True
            continue
        # Italic OFF
        if byte == EBUSTLControlCode.ITALIC_OFF:
            if italic:
                flush_segment()
                italic = False
            continue
        # Underline ON
        if byte == EBUSTLControlCode.UNDERLINE_ON:
            if not underline:
                flush_segment()
                underline = True
            continue
        # Underline OFF
        if byte == EBUSTLControlCode.UNDERLINE_OFF:
            if underline:
                flush_segment()
                underline = False
            continue
        # Boxing ON (some implementations use for bold)
        if byte == EBUSTLControlCode.BOXING_ON:
            if not bold:
                flush_segment()
                bold = True
            continue
        # Boxing OFF
        if byte == EBUSTLControlCode.BOXING_OFF:
            if bold:
                flush_segment()
                bold = False
            continue
        # New line
        if byte == EBUSTLControlCode.NEWLINE:
            # Collapse consecutive newlines to match subtitle rendering behavior
            # Check if last character in current segment or last segment ends with newline
            last_char_is_newline = (
                current_segment_text and current_segment_text[-1] == "\n"
            ) or (
                not current_segment_text
                and segments
                and segments[-1].text.endswith("\n")
            )
            if not last_char_is_newline:
                current_segment_text.append("\n")
                # Flush segment and reset color to white on newline
                # This matches Adobe Premiere behavior where each line starts with default color
                flush_segment()
                current_color = "white"
            continue

        # Printable range – decode using the appropriate character set based on CCT
        if 32 <= byte < 127:
            current_segment_text.append(chr(byte))
        elif 128 <= byte <= 255:
            try:
                current_segment_text.append(bytes([byte]).decode(codec))
            except (UnicodeDecodeError, ValueError):
                # Best‑effort: skip unknown bytes
                continue

    # Flush any remaining text
    flush_segment()

    # Merge consecutive segments with the same style
    merged_segments: List[STLStyledSegment] = []
    for seg in segments:
        if merged_segments and _segments_have_same_style(merged_segments[-1], seg):
            # Merge with previous segment
            merged_segments[-1] = STLStyledSegment(
                text=merged_segments[-1].text + seg.text,
                color=merged_segments[-1].color,
                background_color=merged_segments[-1].background_color,
                italic=merged_segments[-1].italic,
                bold=merged_segments[-1].bold,
                underline=merged_segments[-1].underline,
                flash=merged_segments[-1].flash,
                double_height=merged_segments[-1].double_height,
            )
        else:
            merged_segments.append(seg)

    # Build full text from segments
    full_text = "".join(seg.text for seg in merged_segments)

    # Determine the "primary" style (last segment's style or most common)
    # For backwards compatibility, we return the last active style
    final_color = merged_segments[-1].color if merged_segments else None
    final_bg = merged_segments[-1].background_color if merged_segments else None
    final_italic = merged_segments[-1].italic if merged_segments else False
    final_bold = merged_segments[-1].bold if merged_segments else False
    final_underline = merged_segments[-1].underline if merged_segments else False
    final_flash = merged_segments[-1].flash if merged_segments else False
    final_double_height = (
        merged_segments[-1].double_height if merged_segments else False
    )

    return {
        "text": full_text,
        "color": final_color,
        "background_color": final_bg,
        "italic": final_italic,
        "bold": final_bold,
        "underline": final_underline,
        "flash": final_flash,
        "double_height": final_double_height,
        "segments": merged_segments,
    }
