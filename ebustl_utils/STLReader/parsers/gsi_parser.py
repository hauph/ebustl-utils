from typing import Dict, Any, Tuple, Optional


from ebustl_utils.models import EBU_LANGUAGE_CODES


def decode_language_code(lc_raw: bytes) -> Optional[str]:
    """
    Decode EBU language code from 2-byte field.
    The field contains a hex value as ASCII (e.g., "09" for English).
    """
    try:
        lc_str = lc_raw.decode("ascii", errors="ignore").strip()
        if not lc_str:
            return None
        lc_int = int(lc_str, 16)
        return EBU_LANGUAGE_CODES.get(lc_int)
    except (ValueError, KeyError):
        return None


def derive_fps_from_dfc(dfc: str) -> float:
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
# General Subtitle Information (GSI) parsing
# ------------------------------------------------------------------ #
def parse_gsi(gsi: bytes) -> Tuple[Dict[str, Any], float]:
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
    cct = _safe_str(gsi[12:14])

    # Language Code (LC) - 2 bytes at offset 14-15 (EBU hex code -> ISO 639-1)
    lc = decode_language_code(gsi[14:16])  # e.g., 0x09 -> "en"

    fps = derive_fps_from_dfc(dfc)

    info: Dict[str, Any] = {
        "disk_format_code": dfc,
        "title": tpn,
        "programme_name": tna,
        "character_code_table": cct,
        "language": lc if lc else None,
        "frame_rate": fps,
    }

    return info, fps
