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

from typing import List, Optional

from ebustl_utils.models import STLCaption
from .decoder import decode_stl_file


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

        self._fps = fps_override
        self._captions: Optional[List[STLCaption]] = None
        self._result = None
        self._language = None
        self._gsi = None

    @property
    def captions(self):
        """Parsed captions data (read-only)."""
        return self._captions

    @property
    def fps(self):
        """Frame rate (read-only)."""
        return self._fps

    # @property
    # def drop_frame(self):
    #     """Drop frame flag (read-only)."""
    #     return self._drop_frame

    @property
    def language(self):
        """Language (read-only)."""
        return self._language

    @property
    def gsi(self):
        """GSI (read-only)."""
        return self._gsi

    @property
    def result(self):
        """Original decode result (read-only)."""
        return self._result

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def read(self, raw: bytes):
        result = decode_stl_file(raw, self._fps)
        self._result = result
        self._captions = result["captions"]
        self._gsi = result["gsi"]

        fps = result["fps"]
        self._fps = fps if fps != self._fps else self._fps
