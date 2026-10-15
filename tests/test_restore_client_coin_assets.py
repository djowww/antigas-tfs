import json
import pathlib
import struct
import tempfile
import unittest
import zipfile

from tools import restore_client_coin_assets as assets


DAT_SIGNATURE = 0x439D5A33
SPR_SIGNATURE = 0x439852BE
COIN_ID = 5130
COIN_SPRITES = tuple(range(10, 17))
SPRITE_COUNT = 32


def _thing_record(sprite_ids=(1,), attributes=b"\xff"):
    return attributes + bytes((1, 1, 1, 1, 1, 1, len(sprite_ids))) + struct.pack("<" + "H" * len(sprite_ids), *sprite_ids)


def _dat(coin_sprite_ids=COIN_SPRITES, duplicate_sprite_reference=False):
    data = bytearray(struct.pack("<IHHHH", DAT_SIGNATURE, COIN_ID + 1, 1, 1, 1))
    for item_id in range(100, COIN_ID + 1):
        if item_id == 100:
            data.extend(_thing_record((1,), b"\x00\x2c\x01\xff"))
        elif item_id == 101:
            data.extend(_thing_record((1,), b"\x15\x02\x00\x34\x12\xff"))
        elif item_id == 102:
            data.extend(_thing_record((1,), b"\x18\x02\x00\x03\x00\xff"))
        elif item_id == 103:
            data.extend(_thing_record((1,), b"\x19\x04\x00\xff"))
        elif item_id == 104:
            data.extend(_thing_record((1,), b"\x1c\x05\x00\xff"))
        elif item_id == 105:
            data.extend(_thing_record((1,), b"\x08\x06\x00\xff"))
        elif item_id == 106:
            data.extend(_thing_record((1,), b"\x09\x07\x00\xff"))
        elif item_id == 107:
            data.extend(_thing_record((1,), b"\x1d\x08\x00\xff"))
        elif item_id == 108 and duplicate_sprite_reference:
            data.extend(_thing_record((COIN_SPRITES[0],)))
        elif item_id == COIN_ID:
            data.extend(_thing_record(coin_sprite_ids, b"\x05\x10\xff"))
        else:
            data.extend(_thing_record())
    return bytes(data)


def _spr(entries):
    header_size = 6 + SPRITE_COUNT * 4
    offsets = [0] * SPRITE_COUNT
    records = bytearray()
    for sprite_id in sorted(entries):
        record = b"\xff\x00\xff" + struct.pack("<H", len(entries[sprite_id])) + entries[sprite_id]
        offsets[sprite_id - 1] = header_size + len(records)
        records.extend(record)
    return struct.pack("<IH", SPR_SIGNATURE, SPRITE_COUNT) + struct.pack("<" + "I" * SPRITE_COUNT, *offsets) + records


def _archive(path, version, dat, spr):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("client.version", f"{version}\n")
        archive.writestr("init.lua", f"APP_VERSION = {version}\r\nSERVER_VERSION = 772\r\n")
        archive.writestr("data/things/772/Tibia.dat", dat)
        archive.writestr("data/things/772/Tibia.spr", spr)
        archive.writestr("data/keep.txt", "unchanged client file")


class RestoreClientCoinAssetsTests(unittest.TestCase):
    def setUp(self):
        self.source_dat = _dat(COIN_SPRITES)
        self.target_dat = _dat((0,) * len(COIN_SPRITES))
        self.source_spr = _spr({1: b"shared", **{sid: f"source-{sid}".encode() for sid in COIN_SPRITES}})
        self.target_spr = _spr({1: b"shared"})

    def test_restores_only_coin_record_and_its_sprite_slots(self):
        output_dat, output_spr, report = assets.restore_assets(
            self.source_dat, self.source_spr, self.target_dat, self.target_spr
        )

        target_doc = assets.parse_dat(self.target_dat)
        output_doc = assets.parse_dat(output_dat)
        changed = [item_id for item_id in target_doc.records if target_doc.records[item_id].raw != output_doc.records[item_id].raw]
        self.assertEqual(changed, [COIN_ID])
        self.assertEqual(output_doc.records[COIN_ID].sprite_ids, COIN_SPRITES)
        self.assertEqual(report["changed_item_ids"], [COIN_ID])
        self.assertEqual(report["changed_sprite_ids"], list(COIN_SPRITES))

        header_end = 6 + SPRITE_COUNT * 4
        self.assertEqual(output_spr[header_end:len(self.target_spr)], self.target_spr[header_end:])
        self.assertEqual(output_spr[:6], self.target_spr[:6])
        output_offsets = assets.parse_spr(output_spr)
        source_offsets = assets.parse_spr(self.source_spr)
        for sprite_id in COIN_SPRITES:
            self.assertNotEqual(output_offsets[sprite_id], 0)
            self.assertEqual(
                assets.sprite_record(output_spr, output_offsets[sprite_id]),
                assets.sprite_record(self.source_spr, source_offsets[sprite_id]),
            )
        for sprite_id in range(1, SPRITE_COUNT + 1):
            if sprite_id not in COIN_SPRITES:
                self.assertEqual(output_offsets[sprite_id], assets.parse_spr(self.target_spr)[sprite_id])

    def test_rejects_unknown_attribute_and_truncated_record_bounds(self):
        unknown = bytearray(self.target_dat)
        unknown[12] = 34
        with self.assertRaises(assets.AssetFormatError):
            assets.parse_dat(bytes(unknown))

        with self.assertRaises(assets.AssetFormatError):
            assets.parse_dat(self.target_dat[:-1])

    def test_rejects_out_of_range_and_shared_coin_sprite_references(self):
        bad_refs = _dat((SPRITE_COUNT + 1,) + COIN_SPRITES[1:])
        with self.assertRaises(assets.AssetFormatError):
            assets.restore_assets(bad_refs, self.source_spr, self.target_dat, self.target_spr)

        shared_refs = _dat(COIN_SPRITES, duplicate_sprite_reference=True)
        with self.assertRaises(assets.AssetFormatError):
            assets.restore_assets(shared_refs, self.source_spr, self.target_dat, self.target_spr)

    def test_audit_report_contains_hashes_and_ids_without_asset_bytes(self):
        output_dat, output_spr, report = assets.restore_assets(
            self.source_dat, self.source_spr, self.target_dat, self.target_spr
        )
        encoded = json.dumps(report)
        self.assertRegex(report["source_sha256"]["dat"], r"\A[0-9a-f]{64}\Z")
        self.assertRegex(report["output_sha256"]["spr"], r"\A[0-9a-f]{64}\Z")
        self.assertIn('"changed_item_ids": [5130]', encoded)
        self.assertNotIn("source_bytes", report)
        self.assertNotIn("target_bytes", report)
        self.assertNotIn(self.source_spr.hex(), encoded)
        self.assertTrue(output_dat)
        self.assertTrue(output_spr)

    def test_client_archive_builder_refuses_to_overwrite_existing_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            source_zip = root / "v71.zip"
            target_zip = root / "v74.zip"
            _archive(source_zip, 71, self.source_dat, self.source_spr)
            _archive(target_zip, 74, self.target_dat, self.target_spr)
            output = root / "release"

            assets.build_client(source_zip, target_zip, output, strict_release=False)
            client = output / "client-v75"
            self.assertEqual((client / "data/things/772/Tibia.dat").read_bytes(), assets.restore_assets(
                self.source_dat, self.source_spr, self.target_dat, self.target_spr
            )[0])
            self.assertEqual(
                (client / "init.lua").read_bytes(), b"APP_VERSION = 75\r\nSERVER_VERSION = 772\r\n"
            )
            self.assertEqual((client / "data/keep.txt").read_text(encoding="utf-8"), "unchanged client file")
            self.assertTrue((output / "asset-restoration-report.json").is_file())
            with self.assertRaises(assets.OutputExistsError):
                assets.build_client(source_zip, target_zip, output, strict_release=False)


if __name__ == "__main__":
    unittest.main()
