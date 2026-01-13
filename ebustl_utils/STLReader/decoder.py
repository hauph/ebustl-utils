import io
import warnings
from typing import Any, Dict, List, Optional

from .parsers.gsi_parser import parse_gsi
from .parsers.tti_parser import parse_tti_blocks
from .STLValidationWarning import STLValidationWarning


def decode_stl_file(raw: bytes, fps_override: Optional[float]) -> Dict[str, Any]:
    """
    Parse STL binary bytes and return a caption payload
    """
    if not raw:
        raise ValueError("STL raw data in bytes is required")

    if len(raw) < 1024:
        raise ValueError(f"STL file too short to contain GSI header: {len(raw)} bytes")

    # Validate EBU-STL format by checking Disk Format Code (DFC) at bytes 3-11
    # Valid DFC starts with "STL" (e.g., "STL25.01", "STL30.01", "STL24.01")
    dfc = raw[3:11].decode("ascii", errors="ignore").strip().upper()
    if not dfc.startswith("STL"):
        raise ValueError(
            f"Invalid EBU-STL file: Disk Format Code '{dfc}' does not start with 'STL'. "
            "This file does not appear to be a valid EBU-STL subtitle file."
        )

    buffer = io.BytesIO(raw)

    # GSI block (first 1024 bytes)
    gsi = buffer.read(1024)
    gsi_info, fps = parse_gsi(gsi)

    if fps_override is not None:
        fps = fps_override

    # TTI blocks (remaining 128‑byte records)
    cct = gsi_info.get("character_code_table", "00")
    captions = parse_tti_blocks(buffer, fps, cct)

    # Collect validation issues
    validation_issues: List[str] = []

    # Check TTI block EBN/CS consistency in the first blocks
    # EBN (Extension Block Number) and CS (Cumulative Status) must be consistent:
    # - EBN=0xFF (255) means single block or last block of extension
    # - EBN=0x00 means first block of a multi-block extension
    # - EBN=0x01-0xFE means intermediate block, CS should be 0x02
    # Adobe Premiere tolerates EBN=0 with CS=0 (first block), but rejects
    # intermediate blocks (EBN=1,2,3...) with CS=0.
    tti_data = raw[1024:]
    num_blocks = len(tti_data) // 128
    # Check first 10 blocks (or all if fewer)
    blocks_to_check = min(10, num_blocks)
    ebn_cs_errors_early = 0
    for i in range(blocks_to_check):
        block = tti_data[i * 128 : (i + 1) * 128]
        ebn = block[3]  # Extension Block Number
        cs = block[4]  # Cumulative Status
        # Intermediate blocks (EBN = 1-254) with CS=0 is invalid
        # EBN=0 (first) or EBN=255 (single/last) with CS=0 is tolerated by Adobe
        if 0 < ebn < 0xFF and cs == 0x00:
            ebn_cs_errors_early += 1
    if ebn_cs_errors_early > 0:
        validation_issues.append(
            f"{ebn_cs_errors_early} of first {blocks_to_check} TTI block(s) have intermediate EBN "
            f"(1-254) with invalid CS=0"
        )

    # Emit warning if any validation issues found
    if validation_issues:
        issues_text = "; ".join(validation_issues)
        warnings.warn(
            f"STL file validation issues: {issues_text}. "
            f"This file may fail in strict parsers like Adobe Premiere. "
            f"Parsed {len(captions)} captions successfully.",
            STLValidationWarning,
            stacklevel=3,
        )

    return {
        "captions": [c.to_dict() for c in captions],
        "fps": fps,
        "gsi": gsi_info,
    }
