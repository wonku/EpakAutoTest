from __future__ import annotations

import shutil
import struct
import subprocess
import zipfile
from pathlib import Path


class ApkError(RuntimeError):
    """Raised when APK metadata cannot be read."""


def resolve_package_name(apk_path: str | Path) -> str:
    path = Path(apk_path)
    if not path.exists():
        raise ApkError(f"apk not found: {path}")

    package_name = _package_name_from_aapt(path)
    if package_name:
        return package_name

    return _package_name_from_binary_manifest(path)


def _package_name_from_aapt(apk_path: Path) -> str:
    aapt = shutil.which("aapt")
    if not aapt:
        return ""
    completed = subprocess.run(
        [aapt, "dump", "badging", str(apk_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    if completed.returncode != 0:
        return ""
    first_line = completed.stdout.splitlines()[0] if completed.stdout.splitlines() else ""
    marker = "package: name='"
    if marker not in first_line:
        return ""
    return first_line.split(marker, 1)[1].split("'", 1)[0].strip()


def _package_name_from_binary_manifest(apk_path: Path) -> str:
    with zipfile.ZipFile(apk_path) as apk:
        try:
            data = apk.read("AndroidManifest.xml")
        except KeyError as exc:
            raise ApkError("AndroidManifest.xml not found in APK") from exc

    strings = _read_string_pool(data)
    offset = 8
    while offset + 8 <= len(data):
        chunk_type, header_size, chunk_size = struct.unpack_from("<HHI", data, offset)
        if chunk_size <= 0:
            break
        if chunk_type == 0x0102:
            package_name = _read_start_element_package(data, offset, strings)
            if package_name:
                return package_name
        offset += chunk_size

    raise ApkError("package name not found in AndroidManifest.xml")


def _read_string_pool(data: bytes) -> list[str]:
    offset = 8
    while offset + 28 <= len(data):
        chunk_type, header_size, chunk_size = struct.unpack_from("<HHI", data, offset)
        if chunk_type != 0x0001:
            offset += chunk_size
            continue

        string_count, style_count, flags, strings_start, _styles_start = struct.unpack_from("<IIIII", data, offset + 8)
        offsets_start = offset + header_size
        string_offsets = [
            struct.unpack_from("<I", data, offsets_start + index * 4)[0]
            for index in range(string_count)
        ]
        is_utf8 = bool(flags & 0x00000100)
        strings_base = offset + strings_start
        return [_read_string(data, strings_base + item_offset, is_utf8) for item_offset in string_offsets]

    raise ApkError("string pool not found in AndroidManifest.xml")


def _read_string(data: bytes, offset: int, is_utf8: bool) -> str:
    if is_utf8:
        _, offset = _read_length8(data, offset)
        byte_length, offset = _read_length8(data, offset)
        raw = data[offset: offset + byte_length]
        return raw.decode("utf-8", errors="replace")

    char_length, offset = _read_length16(data, offset)
    raw = data[offset: offset + char_length * 2]
    return raw.decode("utf-16le", errors="replace")


def _read_length8(data: bytes, offset: int) -> tuple[int, int]:
    first = data[offset]
    offset += 1
    if first & 0x80:
        second = data[offset]
        offset += 1
        return ((first & 0x7F) << 8) | second, offset
    return first, offset


def _read_length16(data: bytes, offset: int) -> tuple[int, int]:
    first = struct.unpack_from("<H", data, offset)[0]
    offset += 2
    if first & 0x8000:
        second = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        return ((first & 0x7FFF) << 16) | second, offset
    return first, offset


def _read_start_element_package(data: bytes, offset: int, strings: list[str]) -> str:
    if offset + 36 > len(data):
        return ""
    (
        _chunk_type,
        _header_size,
        _chunk_size,
        _line_number,
        _comment,
        _namespace,
        name_index,
        attribute_start,
        attribute_size,
        attribute_count,
        _id_index,
        _class_index,
        _style_index,
    ) = struct.unpack_from("<HHIIIIIHHHHHH", data, offset)

    if _string_at(strings, name_index) != "manifest":
        return ""

    attributes_offset = offset + attribute_start
    for index in range(attribute_count):
        attr_offset = attributes_offset + index * attribute_size
        if attr_offset + 20 > len(data):
            break
        _attr_namespace, attr_name, raw_value, _typed_size, _typed_zero, data_type, data_value = struct.unpack_from(
            "<IIIHBBI",
            data,
            attr_offset,
        )
        if _string_at(strings, attr_name) != "package":
            continue
        if raw_value != 0xFFFFFFFF:
            return _string_at(strings, raw_value)
        if data_type == 0x03:
            return _string_at(strings, data_value)
    return ""


def _string_at(strings: list[str], index: int) -> str:
    if index == 0xFFFFFFFF or index < 0 or index >= len(strings):
        return ""
    return strings[index]
