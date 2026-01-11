import io
from typing import List, Dict, Any, Optional
import struct
from ebustl_utils.models import JustificationCode, STLCaption
from ebustl_utils.helpers import format_timecode_from_seconds, decode_ebu_stl_text


# ------------------------------------------------------------------ #
# TTI parsing
# ------------------------------------------------------------------ #
def parse_tti_blocks(
    buffer: io.BytesIO, fps: float, cct: str = "00"
) -> List[STLCaption]:
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
        start_tc = format_timecode_from_seconds(start_seconds, fps)
        end_tc = format_timecode_from_seconds(end_seconds, fps)

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

        decoded = decode_ebu_stl_text(text_raw, cct)
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
            entry["double_height"] = entry["double_height"] or decoded["double_height"]
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
