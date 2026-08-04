from __future__ import annotations

import pytest

from app.raw_packet import RawPacketError, pack_raw_packet, unpack_raw_packet


def test_raw_packet_round_trip() -> None:
    header = {"request_id": "abc", "page_index": 2, "text": "Příliš žluťoučký"}
    payload = b"\x89PNG\r\n\x1a\nexample"
    packet = pack_raw_packet(header, payload)
    decoded_header, decoded_payload = unpack_raw_packet(packet)
    assert decoded_header == header
    assert decoded_payload == payload


def test_raw_packet_rejects_incomplete_header() -> None:
    with pytest.raises(RawPacketError):
        unpack_raw_packet(b"\x10\x00\x00\x00{}")
