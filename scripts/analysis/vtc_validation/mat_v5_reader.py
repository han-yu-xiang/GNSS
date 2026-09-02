"""Restricted read-only MATLAB level-5 MAT-file reader.

It supports the numeric, character, cell, and structure arrays used by the
frozen Stage4 ``jointFits`` artifacts.  It deliberately has no write support.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


MI_INT8 = 1
MI_UINT8 = 2
MI_INT16 = 3
MI_UINT16 = 4
MI_INT32 = 5
MI_UINT32 = 6
MI_SINGLE = 7
MI_DOUBLE = 9
MI_INT64 = 12
MI_UINT64 = 13
MI_MATRIX = 14
MI_COMPRESSED = 15
MI_UTF8 = 16
MI_UTF16 = 17
MI_UTF32 = 18

MX_CELL = 1
MX_STRUCT = 2
MX_CHAR = 4
MX_DOUBLE = 6
MX_SINGLE = 7
MX_INT8 = 8
MX_UINT8 = 9
MX_INT16 = 10
MX_UINT16 = 11
MX_INT32 = 12
MX_UINT32 = 13
MX_INT64 = 14
MX_UINT64 = 15

SUPPORTED_CLASSES = {
    MX_CELL, MX_STRUCT, MX_CHAR, MX_DOUBLE, MX_SINGLE, MX_INT8, MX_UINT8,
    MX_INT16, MX_UINT16, MX_INT32, MX_UINT32, MX_INT64, MX_UINT64,
}

DTYPES = {
    MI_INT8: "i1",
    MI_UINT8: "u1",
    MI_INT16: "i2",
    MI_UINT16: "u2",
    MI_INT32: "i4",
    MI_UINT32: "u4",
    MI_SINGLE: "f4",
    MI_DOUBLE: "f8",
    MI_INT64: "i8",
    MI_UINT64: "u8",
}


@dataclass
class _Element:
    data_type: int
    payload: bytes


class _Parser:
    def __init__(self, data: bytes, endian: str = "<") -> None:
        self.data = data
        self.endian = endian
        self.offset = 0

    def remaining(self) -> int:
        return len(self.data) - self.offset

    def read_element(self) -> _Element:
        if self.remaining() < 8:
            raise ValueError("truncated MAT data-element tag")
        first = struct.unpack_from(self.endian + "I", self.data, self.offset)[0]
        if first >> 16:
            data_type = first & 0xFFFF
            size = first >> 16
            payload = self.data[self.offset + 4 : self.offset + 4 + size]
            self.offset += 8
            return _Element(data_type, payload)
        data_type, size = struct.unpack_from(self.endian + "II", self.data, self.offset)
        start = self.offset + 8
        end = start + size
        if end > len(self.data):
            raise ValueError("truncated MAT data-element payload")
        payload = self.data[start:end]
        # MATLAB's writer stores consecutive miCOMPRESSED elements without the
        # ordinary eight-byte payload padding used by uncompressed elements.
        self.offset = end if data_type == MI_COMPRESSED else end + ((8 - size % 8) % 8)
        return _Element(data_type, payload)


def _primitive(element: _Element, endian: str) -> np.ndarray:
    if element.data_type not in DTYPES:
        raise ValueError(f"unsupported MAT primitive type {element.data_type}")
    dtype = np.dtype(endian + DTYPES[element.data_type])
    return np.frombuffer(element.payload, dtype=dtype).copy()


def _shape(values: np.ndarray, dimensions: tuple[int, ...]) -> Any:
    if values.size == 0:
        return values.reshape(dimensions, order="F")
    array = values.reshape(dimensions, order="F")
    if array.size == 1:
        return array.reshape(-1)[0].item()
    return np.squeeze(array)


def _decode_matrix(payload: bytes, endian: str) -> tuple[str, Any]:
    parser = _Parser(payload, endian)
    flags = _primitive(parser.read_element(), endian)
    if flags.size < 2:
        raise ValueError("invalid MAT array flags")
    class_id = int(flags[0]) & 0xFF
    is_complex = bool(int(flags[0]) & 0x0800)
    is_logical = bool(int(flags[0]) & 0x0200)
    dimensions_raw = _primitive(parser.read_element(), endian).astype(int)
    dimensions = tuple(int(value) for value in dimensions_raw)
    if not dimensions:
        dimensions = (0, 0)
    name_element = parser.read_element()
    name = name_element.payload.decode("latin1").rstrip("\x00")
    element_count = int(np.prod(dimensions, dtype=np.int64))

    if class_id == MX_CELL:
        values = []
        for _ in range(element_count):
            child = parser.read_element()
            if child.data_type != MI_MATRIX:
                raise ValueError("MAT cell member is not a matrix")
            values.append(_decode_matrix(child.payload, endian)[1])
        return name, values

    if class_id == MX_STRUCT:
        field_length_values = _primitive(parser.read_element(), endian)
        if field_length_values.size != 1:
            raise ValueError("invalid MAT structure field-name length")
        field_length = int(field_length_values[0])
        field_payload = parser.read_element().payload
        if field_length <= 0 or len(field_payload) % field_length:
            raise ValueError("invalid MAT structure field-name table")
        fields = [
            field_payload[index : index + field_length].split(b"\x00", 1)[0].decode("latin1")
            for index in range(0, len(field_payload), field_length)
        ]
        structures = [dict() for _ in range(element_count)]
        for structure in structures:
            for field in fields:
                child = parser.read_element()
                if child.data_type != MI_MATRIX:
                    raise ValueError("MAT structure field is not a matrix")
                structure[field] = _decode_matrix(child.payload, endian)[1]
        return name, structures[0] if element_count == 1 else structures

    if class_id == MX_CHAR:
        element = parser.read_element()
        if element.data_type in (MI_UTF8, MI_INT8, MI_UINT8):
            text = element.payload.decode("utf-8", errors="replace")
        else:
            codes = _primitive(element, endian).astype(np.uint32)
            text = "".join(chr(int(code)) for code in codes if code)
        return name, text

    supported_numeric = {
        MX_DOUBLE, MX_SINGLE, MX_INT8, MX_UINT8, MX_INT16, MX_UINT16,
        MX_INT32, MX_UINT32, MX_INT64, MX_UINT64,
    }
    if class_id not in supported_numeric:
        raise ValueError(f"unsupported MATLAB array class {class_id}")
    real = _primitive(parser.read_element(), endian)
    if is_complex:
        imaginary = _primitive(parser.read_element(), endian)
        real = real + 1j * imaginary
    if is_logical:
        real = real.astype(bool)
    return name, _shape(real, dimensions)


def _matrix_class_id(payload: bytes, endian: str) -> int:
    parser = _Parser(payload, endian)
    flags = _primitive(parser.read_element(), endian)
    if flags.size < 1:
        raise ValueError("invalid MAT array flags")
    return int(flags[0]) & 0xFF


def _parse_stream(data: bytes, endian: str) -> dict[str, Any]:
    parser = _Parser(data, endian)
    variables: dict[str, Any] = {}
    while parser.remaining() >= 8:
        element = parser.read_element()
        if element.data_type == MI_COMPRESSED:
            variables.update(_parse_stream(zlib.decompress(element.payload), endian))
        elif element.data_type == MI_MATRIX:
            # Stage4 MAT files also contain top-level MCOS table wrappers.  The
            # validation reads the independent numeric/cell/struct jointFits
            # variable and intentionally does not deserialize MATLAB objects.
            if _matrix_class_id(element.payload, endian) not in SUPPORTED_CLASSES:
                continue
            name, value = _decode_matrix(element.payload, endian)
            variables[name] = value
    return variables


def load_mat_v5(path: str | Path) -> dict[str, Any]:
    raw = Path(path).read_bytes()
    if len(raw) < 128 or not raw.startswith(b"MATLAB 5.0 MAT-file"):
        raise ValueError(f"not a MATLAB level-5 MAT file: {path}")
    marker = raw[126:128]
    if marker == b"IM":
        endian = "<"
    elif marker == b"MI":
        endian = ">"
    else:
        raise ValueError("invalid MAT endian marker")
    return _parse_stream(raw[128:], endian)
