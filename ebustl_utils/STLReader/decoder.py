import io
from typing import Any, Dict, Optional

from .parsers.gsi_parser import parse_gsi
from .parsers.tti_blocks_parser import parse_tti_blocks


def decode_stl_file(raw: bytes, fps_override: Optional[float]) -> Dict[str, Any]:
    """
    Parse STL binary bytes and return a caption payload
    """
    if not raw:
        raise ValueError("STL raw data in bytes is required")

    if len(raw) < 1024:
        raise ValueError(f"STL file too short to contain GSI header: {len(raw)} bytes")

    buffer = io.BytesIO(raw)

    # GSI block (first 1024 bytes)
    gsi = buffer.read(1024)
    gsi_info, fps = parse_gsi(gsi)

    if fps_override is not None:
        fps = fps_override

    # TTI blocks (remaining 128‑byte records)
    captions = parse_tti_blocks(buffer, fps)

    return {
        "captions": [c.to_dict() for c in captions],
        "fps": fps,
        "gsi": gsi_info,
    }
