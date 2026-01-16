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
    justification: Optional["JustificationCode"] = (
        None  # Detected from original whitespace
    )

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
# Simple Data Structure for Video Info
# =============================================================================


@dataclass
class VideoInfo:
    """Video timing information from MXF."""

    duration_seconds: float
    frame_rate: float
    total_frames: int
    start_timecode: str  # e.g. "00:00:00:00"


# =============================================================================
# STL Caption Data Structures with Formatting
# =============================================================================


@dataclass
class STLStyledSegment:
    """A segment of text with inline styling for STL captions.

    Used to represent text with multiple styles within a single caption,
    e.g., "blue green" where "blue" is colored blue and "green" is colored green.
    """

    text: str
    color: Optional[str] = None
    background_color: Optional[str] = None
    italic: bool = False
    bold: bool = False
    underline: bool = False
    flash: bool = False
    double_height: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result: Dict[str, Any] = {"text": self.text}
        style: Dict[str, Any] = {}
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
        if style:
            result["style"] = style
        return result


@dataclass
class STLCaption:
    """A single subtitle caption with formatting and layout."""

    start: int  # microseconds
    end: int  # microseconds
    text: str
    start_timecode: str
    end_timecode: str
    # Style attributes (CCS-like styling) - used when no inline segments
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
    # Styled segments for inline styling (e.g., multi-color text)
    segments: Optional[List["STLStyledSegment"]] = None

    def to_dict(self) -> Dict[str, Any]:
        # Check if we have inline styled segments with multiple styles
        has_inline_styles = self.segments and len(self.segments) > 1

        # Build style dict only if there are styling attributes (for single-style captions)
        style: Optional[Dict[str, Any]] = None
        if not has_inline_styles:
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

        result = {
            "start": self.start,
            "start_timecode": self.start_timecode,
            "end": self.end,
            "end_timecode": self.end_timecode,
            "text": self.text,
            "style": style,
            "layout": layout,
        }

        # Include segments when there are inline styles
        if has_inline_styles:
            result["segments"] = [seg.to_dict() for seg in self.segments]

        return result


# EBU Tech 3264 Language Code mapping (hex code -> ISO 639-1)
EBU_LANGUAGE_CODES: Dict[int, str] = {
    0x00: "",  # Unknown/not specified
    0x01: "sq",  # Albanian
    0x02: "br",  # Breton
    0x03: "ca",  # Catalan
    0x04: "hr",  # Croatian
    0x05: "cy",  # Welsh
    0x06: "cs",  # Czech
    0x07: "da",  # Danish
    0x08: "de",  # German
    0x09: "en",  # English
    0x0A: "es",  # Spanish
    0x0B: "eo",  # Esperanto
    0x0C: "et",  # Estonian
    0x0D: "eu",  # Basque
    0x0E: "fo",  # Faroese
    0x0F: "fr",  # French
    0x10: "fy",  # Frisian
    0x11: "ga",  # Irish
    0x12: "gd",  # Gaelic (Scottish)
    0x13: "gl",  # Galician
    0x14: "is",  # Icelandic
    0x15: "it",  # Italian
    0x16: "lb",  # Luxembourgish
    0x17: "lt",  # Lithuanian
    0x18: "lv",  # Latvian
    0x19: "mk",  # Macedonian
    0x1A: "mt",  # Maltese
    0x1B: "nl",  # Dutch
    0x1C: "no",  # Norwegian
    0x1D: "oc",  # Occitan
    0x1E: "pl",  # Polish
    0x1F: "pt",  # Portuguese
    0x20: "ro",  # Romanian
    0x21: "rm",  # Romansh
    0x22: "sr",  # Serbian
    0x23: "sk",  # Slovak
    0x24: "sl",  # Slovenian
    0x25: "fi",  # Finnish
    0x26: "sv",  # Swedish
    0x27: "tr",  # Turkish
    0x28: "nl-BE",  # Flemish
    0x29: "wa",  # Walloon
    # Extended codes (0x7F+)
    0x7F: "am",  # Amharic
    0x80: "ar",  # Arabic
    0x81: "hy",  # Armenian
    0x82: "as",  # Assamese
    0x83: "az",  # Azerbaijani
    0x84: "bm",  # Bambara
    0x85: "be",  # Belarusian
    0x86: "bn",  # Bengali
    0x87: "bg",  # Bulgarian
    0x88: "my",  # Burmese
    0x89: "zh",  # Chinese
    0x8A: "cpe",  # Creole (generic)
    0x8B: "ka",  # Georgian
    0x8C: "el",  # Greek
    0x8D: "gu",  # Gujarati
    0x8E: "gn",  # Guarani
    0x8F: "ha",  # Hausa
    0x90: "he",  # Hebrew
    0x91: "hi",  # Hindi
    0x92: "id",  # Indonesian
    0x93: "ja",  # Japanese
    0x94: "kn",  # Kannada
    0x95: "kk",  # Kazakh
    0x96: "km",  # Khmer
    0x97: "ko",  # Korean
    0x98: "lo",  # Lao
    0x99: "la",  # Latin
    0x9A: "ms",  # Malay
    0x9B: "ml",  # Malayalam
    0x9C: "mr",  # Marathi
    0x9D: "mo",  # Moldavian
    0x9E: "ne",  # Nepali
    0x9F: "or",  # Oriya
    0xA0: "pap",  # Papiamento
    0xA1: "fa",  # Persian
    0xA2: "pa",  # Punjabi
    0xA3: "ps",  # Pushto
    0xA4: "qu",  # Quechua
    0xA5: "ru",  # Russian
    0xA6: "sm",  # Samoan
    0xA7: "sn",  # Shona
    0xA8: "si",  # Sinhalese
    0xA9: "so",  # Somali
    0xAA: "sw",  # Swahili
    0xAB: "tl",  # Tagalog
    0xAC: "ta",  # Tamil
    0xAD: "te",  # Telugu
    0xAE: "th",  # Thai
    0xAF: "uk",  # Ukrainian
    0xB0: "ur",  # Urdu
    0xB1: "uz",  # Uzbek
    0xB2: "vi",  # Vietnamese
    0xB3: "zu",  # Zulu
}


# CCT (Character Code Table) to Python codec mapping
CCT_CODECS: Dict[str, str] = {
    "00": "latin-1",  # Latin (ISO 6937 approximated as Latin-1)
    "01": "iso8859-5",  # Latin/Cyrillic
    "02": "iso8859-6",  # Latin/Arabic
    "03": "iso8859-7",  # Latin/Greek
    "04": "iso8859-8",  # Latin/Hebrew
}
