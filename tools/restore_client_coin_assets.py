#!/usr/bin/env python3
"""Restore only the Antigas Coin art into the audited v772 client baseline."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import struct
import sys
import zipfile


FORMAT_VERSION = 772
COIN_ITEM_ID = 5130
DAT_SIGNATURE = 0x439D5A33
SPR_SIGNATURE = 0x439852BE
EXPECTED_DAT_COUNTS = (5301, 266, 32, 19)
EXPECTED_SPRITE_COUNT = 26487
EXPECTED_COIN_SPRITES = tuple(range(19819, 19826))
DAT_ENTRY = "data/things/772/Tibia.dat"
SPR_ENTRY = "data/things/772/Tibia.spr"

# These hashes pin the exact v71 source and v74 target assets audited for this
# release. The executable CLI refuses a different archive even if its header
# happens to look compatible.
RELEASE_ASSET_HASHES = {
    "source": {
        "dat": "94016df3bd8c6f8872bbeb2e248fa5b36653aa05b7ea451af6bf56a991d946d4",
        "spr": "522b9b2dd71157670621e7c2d9aca321d875ee8cb853d672b1b9f33ac4d2adff",
    },
    "target": {
        "dat": "c3eac36149051224efe93728e91e9979c0ecca2ecf4b28209433be4fe22bee14",
        "spr": "5da002417fd8e2a2fbeb0a8a0ac02010655888a361a44b4ae9bfa4631628e13f",
    },
}

ATTRIBUTE_PAYLOAD_BYTES = {
    0: 2,   # ground speed
    8: 2,   # writable length
    9: 2,   # writable-once length
    21: 4,  # light intensity and color
    24: 4,  # displacement x/y in the v772 format
    25: 2,  # elevation
    28: 2,  # minimap color
    29: 2,  # lens help
}
MAX_THING_SPRITES = 4096
MAX_ZIP_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024


class AssetFormatError(ValueError):
    """An input asset does not match the audited legacy client format."""


class OutputExistsError(FileExistsError):
    """The requested output path already exists and will not be overwritten."""


@dataclass(frozen=True)
class ThingRecord:
    category: str
    thing_id: int
    start: int
    sprite_start: int
    end: int
    sprite_ids: tuple[int, ...]
    raw: bytes


@dataclass(frozen=True)
class DatDocument:
    counts: tuple[int, int, int, int]
    items: dict[int, ThingRecord]
    other_records: dict[tuple[str, int], ThingRecord]
    trailing_bytes: bytes

    @property
    def records(self) -> dict[int, ThingRecord]:
        return self.items

    @property
    def all_records(self) -> dict[tuple[str, int], ThingRecord]:
        result = {("item", item_id): record for item_id, record in self.items.items()}
        result.update(self.other_records)
        return result


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _need(data: bytes, offset: int, count: int, label: str) -> None:
    if offset < 0 or count < 0 or offset + count > len(data):
        raise AssetFormatError(f"{label} exceeds the asset bounds at offset 0x{offset:x}.")


def _read_u8(data: bytes, offset: int, label: str) -> tuple[int, int]:
    _need(data, offset, 1, label)
    return data[offset], offset + 1


def _parse_thing(data: bytes, offset: int, category: str, thing_id: int) -> tuple[ThingRecord, int]:
    start = offset
    attributes: set[int] = set()
    terminated = False

    for _ in range(256):
        attribute, offset = _read_u8(data, offset, f"{category} {thing_id} attributes")
        if attribute == 0xFF:
            terminated = True
            break
        if attribute > 30:
            raise AssetFormatError(
                f"Unsupported v772 attribute {attribute} in {category} {thing_id}."
            )
        if attribute in attributes:
            raise AssetFormatError(f"Duplicate attribute {attribute} in {category} {thing_id}.")
        attributes.add(attribute)
        payload_size = ATTRIBUTE_PAYLOAD_BYTES.get(attribute, 0)
        _need(data, offset, payload_size, f"{category} {thing_id} attribute {attribute}")
        offset += payload_size

    if not terminated:
        raise AssetFormatError(f"Missing attribute terminator in {category} {thing_id}.")

    _need(data, offset, 2, f"{category} {thing_id} dimensions")
    width, height = data[offset], data[offset + 1]
    offset += 2
    if width > 1 or height > 1:
        _need(data, offset, 1, f"{category} {thing_id} real size")
        offset += 1

    _need(data, offset, 5, f"{category} {thing_id} frame metadata")
    layers, pattern_x, pattern_y, pattern_z, phases = data[offset:offset + 5]
    offset += 5
    sprite_count = width * height * layers * pattern_x * pattern_y * pattern_z * phases
    if sprite_count > MAX_THING_SPRITES:
        raise AssetFormatError(f"{category} {thing_id} has an invalid sprite count: {sprite_count}.")

    sprite_start = offset
    sprite_bytes = sprite_count * 2
    _need(data, sprite_start, sprite_bytes, f"{category} {thing_id} sprite references")
    if sprite_count:
        sprite_ids = struct.unpack_from("<" + "H" * sprite_count, data, sprite_start)
    else:
        sprite_ids = ()
    end = sprite_start + sprite_bytes
    return ThingRecord(category, thing_id, start, sprite_start, end, tuple(sprite_ids), data[start:end]), end


def parse_dat(data: bytes, *, expected_counts: tuple[int, int, int, int] | None = None) -> DatDocument:
    if len(data) < 12:
        raise AssetFormatError("DAT header is truncated.")
    signature, item_count, outfit_count, effect_count, missile_count = struct.unpack_from("<IHHHH", data)
    if signature != DAT_SIGNATURE:
        raise AssetFormatError(f"Unsupported DAT signature: 0x{signature:08x}.")
    counts = (item_count, outfit_count, effect_count, missile_count)
    if expected_counts is not None and counts != expected_counts:
        raise AssetFormatError(f"Unexpected DAT counts: {counts}; expected {expected_counts}.")
    if item_count < 100 or outfit_count < 1 or effect_count < 1 or missile_count < 1:
        raise AssetFormatError(f"Invalid DAT category counts: {counts}.")

    specs = (
        ("item", 100, item_count, True),
        ("outfit", 1, outfit_count, False),
        ("effect", 1, effect_count, False),
        ("missile", 1, missile_count, False),
    )
    items: dict[int, ThingRecord] = {}
    other_records: dict[tuple[str, int], ThingRecord] = {}
    offset = 12
    for category, first_id, exclusive_end, is_item in specs:
        for thing_id in range(first_id, exclusive_end):
            record, offset = _parse_thing(data, offset, category, thing_id)
            if is_item:
                items[thing_id] = record
            else:
                other_records[(category, thing_id)] = record
    return DatDocument(counts, items, other_records, data[offset:])


def parse_spr(data: bytes, *, expected_count: int | None = None) -> dict[int, int]:
    if len(data) < 6:
        raise AssetFormatError("SPR header is truncated.")
    signature, sprite_count = struct.unpack_from("<IH", data)
    if signature != SPR_SIGNATURE:
        raise AssetFormatError(f"Unsupported SPR signature: 0x{signature:08x}.")
    if expected_count is not None and sprite_count != expected_count:
        raise AssetFormatError(f"Unexpected SPR sprite count: {sprite_count}; expected {expected_count}.")
    table_end = 6 + sprite_count * 4
    _need(data, 6, sprite_count * 4, "SPR offset table")
    offsets = struct.unpack_from("<" + "I" * sprite_count, data, 6) if sprite_count else ()
    result: dict[int, int] = {}
    for sprite_id, offset in enumerate(offsets, 1):
        result[sprite_id] = offset
        if offset == 0:
            continue
        if offset < table_end:
            raise AssetFormatError(f"SPR sprite {sprite_id} overlaps its offset table.")
        _need(data, offset, 5, f"SPR sprite {sprite_id} header")
        payload_size = struct.unpack_from("<H", data, offset + 3)[0]
        _need(data, offset + 5, payload_size, f"SPR sprite {sprite_id} payload")
    return result


def sprite_record(data: bytes, offset: int) -> bytes:
    _need(data, offset, 5, "SPR sprite record")
    payload_size = struct.unpack_from("<H", data, offset + 3)[0]
    _need(data, offset + 5, payload_size, "SPR sprite payload")
    return data[offset:offset + 5 + payload_size]


def _check_asset_hashes(source_dat: bytes, source_spr: bytes, target_dat: bytes, target_spr: bytes) -> None:
    observed = {
        "source": {"dat": _sha256(source_dat), "spr": _sha256(source_spr)},
        "target": {"dat": _sha256(target_dat), "spr": _sha256(target_spr)},
    }
    if observed != RELEASE_ASSET_HASHES:
        raise AssetFormatError(
            "The input assets are not the audited v71/v74 client files; refusing an unreviewed rewrite."
        )


def restore_assets(
    source_dat: bytes,
    source_spr: bytes,
    target_dat: bytes,
    target_spr: bytes,
    *,
    strict_release: bool = False,
) -> tuple[bytes, bytes, dict[str, object]]:
    if strict_release:
        _check_asset_hashes(source_dat, source_spr, target_dat, target_spr)
        expected_counts = EXPECTED_DAT_COUNTS
        expected_sprite_count = EXPECTED_SPRITE_COUNT
    else:
        expected_counts = None
        expected_sprite_count = None

    source_doc = parse_dat(source_dat, expected_counts=expected_counts)
    target_doc = parse_dat(target_dat, expected_counts=expected_counts)
    if source_doc.counts != target_doc.counts:
        raise AssetFormatError("The source and target DAT category counts differ.")
    source_offsets = parse_spr(source_spr, expected_count=expected_sprite_count)
    target_offsets = parse_spr(target_spr, expected_count=expected_sprite_count)
    if len(source_offsets) != len(target_offsets):
        raise AssetFormatError("The source and target SPR counts differ.")

    source_coin = source_doc.items.get(COIN_ITEM_ID)
    target_coin = target_doc.items.get(COIN_ITEM_ID)
    if source_coin is None or target_coin is None:
        raise AssetFormatError(f"Item {COIN_ITEM_ID} is not present in both DAT files.")
    if source_coin.start != target_coin.start or source_coin.end != target_coin.end:
        raise AssetFormatError("The Coin DAT record bounds differ between v71 and v74.")
    source_prefix_size = source_coin.sprite_start - source_coin.start
    target_prefix_size = target_coin.sprite_start - target_coin.start
    if source_prefix_size != target_prefix_size or source_coin.raw[:source_prefix_size] != target_coin.raw[:target_prefix_size]:
        raise AssetFormatError("The Coin DAT metadata changed; only the art restoration is approved.")
    if len(source_coin.sprite_ids) != len(target_coin.sprite_ids) or not source_coin.sprite_ids:
        raise AssetFormatError("The source and target Coin sprite-reference counts do not match.")
    if any(sprite_id == 0 for sprite_id in source_coin.sprite_ids):
        raise AssetFormatError("The v71 Coin DAT record contains a missing sprite reference.")
    if any(target_coin.sprite_ids):
        raise AssetFormatError("The v74 Coin DAT record is not the expected empty sprite record.")

    sprite_ids = tuple(dict.fromkeys(source_coin.sprite_ids))
    if strict_release and source_coin.sprite_ids != EXPECTED_COIN_SPRITES:
        raise AssetFormatError("The v71 Coin sprite references differ from the audited sequence.")

    collisions: set[int] = set()
    for document in (source_doc, target_doc):
        for key, record in document.all_records.items():
            if key != ("item", COIN_ITEM_ID):
                collisions.update(set(record.sprite_ids).intersection(sprite_ids))
    if collisions:
        raise AssetFormatError(f"Coin sprite slots are shared by other DAT records: {sorted(collisions)}.")

    source_spr_table_end = 6 + len(source_offsets) * 4
    target_spr_table_end = 6 + len(target_offsets) * 4
    if source_spr_table_end != target_spr_table_end:
        raise AssetFormatError("The source and target SPR table bounds differ.")

    source_records: dict[int, bytes] = {}
    for sprite_id in sprite_ids:
        if sprite_id > len(source_offsets):
            raise AssetFormatError(f"Coin sprite reference {sprite_id} exceeds the SPR table.")
        source_offset = source_offsets[sprite_id]
        target_offset = target_offsets[sprite_id]
        if source_offset == 0:
            raise AssetFormatError(f"Source Coin sprite {sprite_id} is absent from v71 SPR.")
        if target_offset != 0:
            raise AssetFormatError(f"Target Coin sprite slot {sprite_id} is already occupied in v74 SPR.")
        source_records[sprite_id] = sprite_record(source_spr, source_offset)

    output_dat = bytearray(target_dat)
    output_dat[target_coin.start:target_coin.end] = source_coin.raw
    if len(output_dat) != len(target_dat):
        raise AssetFormatError("Restoring the Coin DAT record changed the DAT file length.")

    output_spr = bytearray(target_spr)
    appended = bytearray()
    output_offsets = dict(target_offsets)
    for sprite_id in sprite_ids:
        offset = len(output_spr) + len(appended)
        if offset > 0xFFFFFFFF:
            raise AssetFormatError("Restored SPR file exceeds the legacy 32-bit offset limit.")
        struct.pack_into("<I", output_spr, 6 + (sprite_id - 1) * 4, offset)
        output_offsets[sprite_id] = offset
        appended.extend(source_records[sprite_id])
    output_spr.extend(appended)

    restored_doc = parse_dat(bytes(output_dat), expected_counts=expected_counts)
    changed_records = [
        thing_id
        for thing_id, record in target_doc.all_records.items()
        if restored_doc.all_records[thing_id].raw != record.raw
    ]
    if changed_records != [("item", COIN_ITEM_ID)]:
        raise AssetFormatError(f"DAT restoration touched unexpected records: {changed_records[:20]}.")
    if restored_doc.trailing_bytes != target_doc.trailing_bytes:
        raise AssetFormatError("DAT restoration changed bytes outside the parsed record tables.")

    verified_offsets = parse_spr(bytes(output_spr), expected_count=expected_sprite_count)
    changed_sprite_slots = [
        sprite_id
        for sprite_id in target_offsets
        if verified_offsets[sprite_id] != target_offsets[sprite_id]
    ]
    if changed_sprite_slots != list(sprite_ids):
        raise AssetFormatError(f"SPR restoration touched unexpected slots: {changed_sprite_slots}.")
    if output_spr[target_spr_table_end:len(target_spr)] != target_spr[target_spr_table_end:]:
        raise AssetFormatError("SPR restoration changed the existing v74 sprite data.")
    for sprite_id in sprite_ids:
        if sprite_record(bytes(output_spr), verified_offsets[sprite_id]) != source_records[sprite_id]:
            raise AssetFormatError(f"Restored SPR record {sprite_id} differs from the audited v71 source.")

    output_dat_bytes = bytes(output_dat)
    output_spr_bytes = bytes(output_spr)
    report: dict[str, object] = {
        "format_version": FORMAT_VERSION,
        "item_id": COIN_ITEM_ID,
        "changed_item_ids": [COIN_ITEM_ID],
        "changed_sprite_ids": list(sprite_ids),
        "source_sha256": {"dat": _sha256(source_dat), "spr": _sha256(source_spr)},
        "target_sha256": {"dat": _sha256(target_dat), "spr": _sha256(target_spr)},
        "output_sha256": {"dat": _sha256(output_dat_bytes), "spr": _sha256(output_spr_bytes)},
        "coin_record_sha256": {
            "source": _sha256(source_coin.raw),
            "target": _sha256(target_coin.raw),
            "output": _sha256(restored_doc.items[COIN_ITEM_ID].raw),
        },
    }
    return output_dat_bytes, output_spr_bytes, report


def _read_archive_assets(archive_path: str | Path, expected_version: int) -> tuple[bytes, bytes]:
    try:
        archive = zipfile.ZipFile(archive_path)
    except (OSError, zipfile.BadZipFile) as error:
        raise AssetFormatError(f"Could not open client archive: {error}") from error
    with archive:
        total_uncompressed = sum(info.file_size for info in archive.infolist())
        if total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
            raise AssetFormatError("Client archive exceeds the supported uncompressed size.")
        damaged = archive.testzip()
        if damaged:
            raise AssetFormatError(f"Client archive has a CRC error in {damaged}.")
        for required in ("client.version", "init.lua", DAT_ENTRY, SPR_ENTRY):
            if required not in archive.namelist():
                raise AssetFormatError(f"Client archive is missing {required}.")
        version_text = archive.read("client.version").decode("ascii", "strict").strip()
        if version_text != str(expected_version):
            raise AssetFormatError(f"Expected v{expected_version} client archive, found {version_text!r}.")
        init_text = archive.read("init.lua").decode("utf-8", "strict")
        app_match = re.search(r"(?m)^\s*APP_VERSION\s*=\s*(\d+)\b", init_text)
        server_match = re.search(r"(?m)^\s*SERVER_VERSION\s*=\s*(\d+)\b", init_text)
        if not app_match or int(app_match.group(1)) != expected_version:
            raise AssetFormatError(f"Client init.lua does not identify release v{expected_version}.")
        if not server_match or int(server_match.group(1)) != FORMAT_VERSION:
            raise AssetFormatError(f"Client init.lua does not identify the audited v{FORMAT_VERSION} data format.")
        return archive.read(DAT_ENTRY), archive.read(SPR_ENTRY)


def audit_client_archives(
    source_archive: str | Path,
    target_archive: str | Path,
    *,
    strict_release: bool = True,
) -> dict[str, object]:
    source_dat, source_spr = _read_archive_assets(source_archive, 71)
    target_dat, target_spr = _read_archive_assets(target_archive, 74)
    _, _, report = restore_assets(
        source_dat, source_spr, target_dat, target_spr, strict_release=strict_release
    )
    report["source_client_version"] = 71
    report["target_client_version"] = 74
    report["output_client_version"] = 75
    return report


def _safe_extract_client(archive_path: str | Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    seen_files: set[str] = set()
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            name = info.filename
            if "\\" in name:
                raise AssetFormatError(f"Unsafe backslash path in client archive: {name!r}.")
            relative = PurePosixPath(name)
            if relative.is_absolute() or not relative.parts or any(part in ("", ".", "..") for part in relative.parts):
                raise AssetFormatError(f"Unsafe path in client archive: {name!r}.")
            if any(":" in part for part in relative.parts):
                raise AssetFormatError(f"Drive-qualified path in client archive: {name!r}.")
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise AssetFormatError(f"Symbolic links are not allowed in client archives: {name!r}.")

            target = destination.joinpath(*relative.parts)
            resolved = target.resolve()
            if destination.resolve() not in resolved.parents and resolved != destination.resolve():
                raise AssetFormatError(f"Client archive path escapes its staging directory: {name!r}.")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            normalized = relative.as_posix().casefold()
            if normalized in seen_files:
                raise AssetFormatError(f"Duplicate path in client archive: {name!r}.")
            seen_files.add(normalized)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source, target.open("xb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)


def build_client(
    source_archive: str | Path,
    target_archive: str | Path,
    output_directory: str | Path,
    *,
    strict_release: bool = True,
) -> dict[str, object]:
    output = Path(output_directory).expanduser().absolute()
    if output.exists():
        raise OutputExistsError(f"Output already exists; choose a fresh directory: {output}")

    source_dat, source_spr = _read_archive_assets(source_archive, 71)
    target_dat, target_spr = _read_archive_assets(target_archive, 74)
    restored_dat, restored_spr, report = restore_assets(
        source_dat, source_spr, target_dat, target_spr, strict_release=strict_release
    )

    client_directory = output / "client-v75"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=False)
    _safe_extract_client(target_archive, client_directory)
    (client_directory / DAT_ENTRY).write_bytes(restored_dat)
    (client_directory / SPR_ENTRY).write_bytes(restored_spr)

    init_path = client_directory / "init.lua"
    init_bytes = init_path.read_bytes()
    updated, replacements = re.subn(rb"(?m)^APP_VERSION\s*=\s*\d+", b"APP_VERSION = 75", init_bytes, count=1)
    if replacements != 1:
        raise AssetFormatError("Staged client init.lua does not contain one APP_VERSION field.")
    init_path.write_bytes(updated)
    (client_directory / "client.version").write_text("75\n", encoding="ascii", newline="")

    report["source_client_version"] = 71
    report["target_client_version"] = 74
    report["output_client_version"] = 75
    (output / "asset-restoration-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline=""
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-v71", required=True, type=Path, help="audited v71 client ZIP")
    parser.add_argument("--target-v74", required=True, type=Path, help="audited v74 client ZIP")
    parser.add_argument("--output-directory", type=Path, help="fresh directory for staged client and local report")
    parser.add_argument("--audit-only", action="store_true", help="print hashes and changed IDs without writing assets")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.audit_only:
            report = audit_client_archives(args.source_v71, args.target_v74, strict_release=True)
        else:
            if args.output_directory is None:
                raise AssetFormatError("--output-directory is required unless --audit-only is used.")
            report = build_client(args.source_v71, args.target_v74, args.output_directory, strict_release=True)
        print(json.dumps(report, indent=2, sort_keys=True))
        if not args.audit_only:
            print(f"Staged v75 client: {args.output_directory.absolute() / 'client-v75'}")
            print(f"Local asset report: {args.output_directory.absolute() / 'asset-restoration-report.json'}")
        return 0
    except (AssetFormatError, OutputExistsError, OSError, zipfile.BadZipFile, UnicodeError) as error:
        print(f"client asset restoration failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
