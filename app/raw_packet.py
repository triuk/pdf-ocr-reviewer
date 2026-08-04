from __future__ import annotations

import json
import struct
from typing import Any

_HEADER_LENGTH = struct.Struct("<I")


class RawPacketError(ValueError):
    """Raised when a binary page packet is malformed."""


def pack_raw_packet(header: dict[str, Any], payload: bytes) -> bytes:
    header_bytes = json.dumps(
        header,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(header_bytes) > 0xFFFFFFFF:
        raise RawPacketError("JSON header is too large.")
    return _HEADER_LENGTH.pack(len(header_bytes)) + header_bytes + payload


def unpack_raw_packet(packet: bytes) -> tuple[dict[str, Any], bytes]:
    if len(packet) < _HEADER_LENGTH.size:
        raise RawPacketError("Packet is shorter than its length prefix.")
    (header_length,) = _HEADER_LENGTH.unpack_from(packet, 0)
    header_start = _HEADER_LENGTH.size
    header_end = header_start + header_length
    if header_end > len(packet):
        raise RawPacketError("Packet contains an incomplete JSON header.")
    try:
        header = json.loads(packet[header_start:header_end].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RawPacketError("Packet contains an invalid JSON header.") from exc
    if not isinstance(header, dict):
        raise RawPacketError("Packet JSON header must be an object.")
    return header, packet[header_end:]
