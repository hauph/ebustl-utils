"""
EBU STL Models - Data structures and type definitions.

Contains:
- Enums for teletext colors and control codes
- Dataclasses for subtitle content and formatting
- STL caption structures for reader output
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Dict, Optional, Any


# =============================================================================
# Teletext Color Codes
# =============================================================================


class TeletextColor(IntEnum):
    """Teletext Level 1 colors (spacing attributes 0x00-0x07)"""

    BLACK = 0
    RED = 1
    GREEN = 2
    YELLOW = 3
    BLUE = 4
    MAGENTA = 5
    CYAN = 6
    WHITE = 7


# Map teletext color codes to EBU STL color names
TELETEXT_COLOR_NAMES = {
    TeletextColor.BLACK: "black",
    TeletextColor.RED: "red",
    TeletextColor.GREEN: "green",
    TeletextColor.YELLOW: "yellow",
    TeletextColor.BLUE: "blue",
    TeletextColor.MAGENTA: "magenta",
    TeletextColor.CYAN: "cyan",
    TeletextColor.WHITE: "white",
}


# =============================================================================
# Teletext Control Codes
# =============================================================================


class TeletextControlCode(IntEnum):
    """Teletext control codes (0x00-0x1F)"""

    # Alpha colors (foreground)
    ALPHA_BLACK = 0x00
    ALPHA_RED = 0x01
    ALPHA_GREEN = 0x02
    ALPHA_YELLOW = 0x03
    ALPHA_BLUE = 0x04
    ALPHA_MAGENTA = 0x05
    ALPHA_CYAN = 0x06
    ALPHA_WHITE = 0x07

    # Display control
    FLASH = 0x08
    STEADY = 0x09
    END_BOX = 0x0A
    START_BOX = 0x0B
    NORMAL_HEIGHT = 0x0C
    DOUBLE_HEIGHT = 0x0D
    DOUBLE_WIDTH = 0x0E
    DOUBLE_SIZE = 0x0F

    # Mosaic colors
    MOSAIC_BLACK = 0x10
    MOSAIC_RED = 0x11
    MOSAIC_GREEN = 0x12
    MOSAIC_YELLOW = 0x13
    MOSAIC_BLUE = 0x14
    MOSAIC_MAGENTA = 0x15
    MOSAIC_CYAN = 0x16
    MOSAIC_WHITE = 0x17

    # Additional control
    CONCEAL = 0x18
    CONTIGUOUS_MOSAIC = 0x19
    SEPARATED_MOSAIC = 0x1A
    ESC = 0x1B
    BLACK_BACKGROUND = 0x1C
    NEW_BACKGROUND = 0x1D
    HOLD_MOSAIC = 0x1E
    RELEASE_MOSAIC = 0x1F


# =============================================================================
# EBU STL Control Codes (for Text Field)
# =============================================================================


class EBUSTLControlCode(IntEnum):
    """EBU STL Text Field control codes"""

    # Teletext spacing attributes (0x00-0x07 foreground colors)
    ALPHA_BLACK = 0x00
    ALPHA_RED = 0x01
    ALPHA_GREEN = 0x02
    ALPHA_YELLOW = 0x03
    ALPHA_BLUE = 0x04
    ALPHA_MAGENTA = 0x05
    ALPHA_CYAN = 0x06
    ALPHA_WHITE = 0x07

    # Display attributes
    FLASH = 0x08
    STEADY = 0x09
    END_BOX = 0x0A
    START_BOX = 0x0B
    NORMAL_HEIGHT = 0x0C
    DOUBLE_HEIGHT = 0x0D

    # Formatting
    ITALIC_ON = 0x80
    ITALIC_OFF = 0x81
    UNDERLINE_ON = 0x82
    UNDERLINE_OFF = 0x83
    BOXING_ON = 0x84
    BOXING_OFF = 0x85

    # Line break
    NEWLINE = 0x8A

    # Unused space (filler)
    UNUSED_SPACE = 0x8F


# =============================================================================
# Justification Codes
# =============================================================================


class JustificationCode(IntEnum):
    """EBU STL Justification codes"""

    UNCHANGED = 0x00
    LEFT = 0x01
    CENTERED = 0x02
    RIGHT = 0x03


# =============================================================================
# Subtitle Data Structures with Full Formatting
# =============================================================================


@dataclass
class TextSegment:
    """A segment of text with formatting attributes."""

    text: str
    foreground_color: TeletextColor = TeletextColor.WHITE
    background_color: TeletextColor = TeletextColor.BLACK
    double_height: bool = False
    flash: bool = False
    boxing: bool = False
    concealed: bool = False


@dataclass
class SubtitleLine:
    """A single line of subtitle text with full formatting."""

    row: int  # Vertical position (1-24 for teletext)
    segments: List[TextSegment] = field(default_factory=list)
    double_height: bool = False

    @property
    def text(self) -> str:
        """Get plain text without formatting."""
        return "".join(seg.text for seg in self.segments)

    @property
    def has_content(self) -> bool:
        """Check if line has actual content."""
        return bool(self.text.strip())


@dataclass
class Subtitle:
    """A complete subtitle with timing, positioning, and formatted content."""

    index: int
    start_time: int  # In frames (25fps for PAL)
    end_time: int  # In frames
    lines: List[SubtitleLine] = field(default_factory=list)
    justification: JustificationCode = JustificationCode.CENTERED
    vertical_position: int = 20  # Default near bottom

    @property
    def has_content(self) -> bool:
        """Check if subtitle has actual content."""
        return any(line.has_content for line in self.lines)


# =============================================================================
# STL Caption Data Structures with Formatting
# =============================================================================


@dataclass
class STLCaption:
    """A single subtitle caption with formatting and layout."""

    start: int  # microseconds
    end: int  # microseconds
    text: str
    start_timecode: str
    end_timecode: str
    # Style attributes (CCS-like styling)
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
