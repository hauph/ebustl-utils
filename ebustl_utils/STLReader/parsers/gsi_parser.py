from typing import Dict, Any, Tuple


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
# GSI parsing
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
    cct = _safe_str(gsi[12:16])

    fps = derive_fps_from_dfc(dfc)

    info: Dict[str, Any] = {
        "disk_format_code": dfc,
        "title": tpn,
        "programme_name": tna,
        "character_code_table": cct,
        "frame_rate": fps,
    }

    return info, fps
