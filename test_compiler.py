"""Offline deterministic tests, no device/network/target execution or fixture cleanup.
SPDX-License-Identifier: MIT
Run: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s watchface-compiler -v
"""
import copy
import hashlib
import os
from pathlib import Path
import random
import struct
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from PIL import Image
import face_codec as codec
import pack_face as pack
from inspect_face import inspect
from validate_gb import parse_as_watchface

HERE = Path(__file__).resolve().parent
MINIMAL = HERE / 'samples/minimal/UsageProbe.fprj'
# Public reference sample: git clone https://github.com/Vadim170/miband9-minimal-analog
# and point MINIMAL_ANALOG_DIR at it (commit 1249c462986061a7bc1021c5fde513fa276ca193).
REFERENCE = Path(os.environ.get('MINIMAL_ANALOG_DIR', str(HERE/'miband9-minimal-analog')))
if not MINIMAL.exists():
    import make_minimal
    make_minimal.generate(MINIMAL.parent)
REFERENCE_SHA = 'd531249c5c2f2335ce00b464cf75007d82dd0dc750bd26116bbe5fc3187003b3'


class CodecTests(unittest.TestCase):
    def test_primary_colors_and_floor_not_bitshift(self):
        im = Image.new('RGBA', (4, 1))
        im.putdata([(255, 0, 0, 255), (0, 255, 0, 123), (0, 0, 255, 0), (8, 4, 8, 255)])
        self.assertEqual(codec.rgb565a(im).hex(), '00f8ffe0077b1f00000000ff')

    def test_rle_128_identical_pixels(self):
        raw = b'\x01\x02\xff'*128
        self.assertEqual(codec.encode_rle(raw), b'\x7f\x01\x02\xff\x81\x01\x02\xff')

    def test_frame_roundtrip_random_and_runs(self):
        rng = random.Random(914)
        im = Image.new('RGBA', (192, 2))
        im.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(384)])
        self.assertEqual(codec.decode_frame(codec.frame_for(im), 384), codec.rgb565a(im))
        im = Image.new('RGBA', (192, 490), (4, 96, 255, 0))
        self.assertEqual(codec.decode_frame(codec.frame_for(im), 192*490), codec.rgb565a(im))

    def test_decoder_literal_packets(self):
        frame = bytes.fromhex('e021a55a6300000082010203040506')
        self.assertEqual(codec.decode_frame(frame, 2), bytes.fromhex('010203040506'))

    def test_bad_rle(self):
        header = bytes.fromhex('e021a55a33000000')
        for suffix in (b'', b'\0abc', b'\x81ab', b'\x02abc'):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                codec.decode_frame(header+suffix, 1)

    def test_mismatched_list_dimensions(self):
        images = [Image.new('RGBA', (1, 1)), Image.new('RGBA', (2, 1))]
        with patch.object(codec, 'load_png', side_effect=images), self.assertRaises(ValueError):
            codec.image_resource(['one.png','two.png'], True)


class CompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = pack.compile_project(MINIMAL, '914203150')
        cls.meta = inspect(cls.data)

    def test_minimal_gb_gate(self):
        result = parse_as_watchface(self.data)
        self.assertEqual(result['id'], '914203150')
        self.assertEqual(result['name'], 'Usage Probe')
        self.assertEqual(result['preview'], [192, 490])
        self.assertEqual(result['band9_size_gate'], 'resolution_matches')

    def test_required_sources_and_glyphs(self):
        components = self.meta['faces'][0]['components']
        self.assertEqual([c['source'] for c in components if c['kind']=='number'], ['0811','1011','2031','5031'])
        self.assertEqual(len(components), 5)
        self.assertTrue(all(r['frames'] == 11 for r in self.meta['faces'][0]['resources'] if r['frames'] > 1))

    def test_deterministic(self):
        self.assertEqual(self.data, pack.compile_project(MINIMAL, '914203150'))

    def test_id_changes_only_header_digits(self):
        other = pack.compile_project(MINIMAL, '914203151')
        self.assertEqual([i for i,(a,b) in enumerate(zip(self.data, other)) if a != b], [48])

    def test_legacy_hex_source(self):
        self.assertEqual(pack.data_source('40009031'), bytes.fromhex('d031'))
        self.assertEqual(pack.data_source('10009831'), bytes.fromhex('a831'))
        self.assertEqual(pack.data_source('2031'), bytes.fromhex('2031'))

    def test_bad_id_and_source(self):
        for bad in ('abc', '12345678', '１２３４５６７８９', '1234567890'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                pack.compile_project(MINIMAL, bad)
        for bad in ('', 'nope', '../x', '123456789'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                pack.data_source(bad)

    def test_image_path_escape(self):
        with self.assertRaises(ValueError):
            pack.safe_image(MINIMAL.parent/'images', '../UsageProbe.fprj')

    def test_reject_unsupported_project_features(self):
        for attr, value in (('Shape','42'), ('Name','app_weather'), ('Name','anim_[3@100]'),
                            ('Alpha','128'), ('Visible_Src','1'), ('Shape','34')):
            tree = ET.fromstring(MINIMAL.read_text(encoding='utf-8'))
            tree.find('Screen/Widget').set(attr, value)
            with self.subTest(attr=attr,value=value), patch.object(pack.ET, 'fromstring', return_value=tree), self.assertRaises(ValueError):
                pack.parse_project(MINIMAL, MINIMAL.parent)

    def test_reject_wrong_device(self):
        tree = ET.fromstring(MINIMAL.read_text(encoding='utf-8'))
        tree.set('DeviceType', '8')
        with patch.object(pack.ET, 'fromstring', return_value=tree), self.assertRaises(ValueError):
            pack.parse_project(MINIMAL, MINIMAL.parent)

    def test_list_deduplication(self):
        face = pack.parse_project(MINIMAL, MINIMAL.parent)
        face.items[2].paths = face.items[1].paths  # minutes and hours share one atlas
        with patch.object(pack, 'parse_project', return_value=face):
            meta = inspect(pack.compile_project(MINIMAL))
        self.assertEqual(meta['faces'][0]['tables']['3']['count'], 3)

    def test_multiface_global_ids_and_flags(self):
        face = pack.parse_project(MINIMAL, MINIMAL.parent)
        with patch.object(pack, 'find_projects', return_value=(MINIMAL,[MINIMAL,MINIMAL],False)), patch.object(pack, 'parse_project', side_effect=lambda *_: copy.deepcopy(face)):
            meta = inspect(pack.compile_project(MINIMAL))
        self.assertEqual(meta['flags'], 2)
        self.assertEqual(len(meta['faces']), 2)
        ids = [c['widget_id'] for f in meta['faces'] for c in f['components'] if 'widget_id' in c]
        self.assertEqual(len(ids), len(set(ids)))

    def test_reject_corrupt_resource_pointer(self):
        changed = bytearray(self.data)
        table = self.meta['faces'][0]['tables']['2']['offset']
        struct.pack_into('<I', changed, table+8, len(changed)+4)
        with self.assertRaises(ValueError):
            inspect(changed)

    def test_reject_dangling_image_reference(self):
        changed = bytearray(self.data)
        w = next(c for c in self.meta['faces'][0]['components'] if c['kind']=='number')['offset']
        struct.pack_into('<I', changed, w+8, 0x030000ff)
        with self.assertRaises(ValueError):
            inspect(changed)

    def test_gb_reject_nonnumeric_id(self):
        changed = bytearray(self.data)
        changed[40] = ord('X')
        with self.assertRaises(ValueError):
            parse_as_watchface(changed)

    def test_gb_size_gate(self):
        offset, = struct.unpack_from('<I', self.data, 32)
        changed = bytearray(self.data)
        struct.pack_into('<HH', changed, offset+4, 122, 310)
        self.assertEqual(parse_as_watchface(changed)['band9_size_gate'], 'aspect_ratio_matches')
        for dimensions in ((192,192), (384,980), (0,0)):
            struct.pack_into('<HH', changed, offset+4, *dimensions)
            with self.subTest(dimensions=dimensions), self.assertRaises(ValueError):
                parse_as_watchface(changed)

    def test_strict_parser_stronger_than_gb(self):
        changed = bytearray(self.data)
        changed[2] = 0
        self.assertEqual(parse_as_watchface(changed)['gb_parse'], 'PASS')
        with self.assertRaises(ValueError):
            inspect(changed)

    def test_reject_truncations_and_trailing_data(self):
        for changed in (self.data[:40], self.data[:168], self.data[:-8], self.data+b'junk'):
            with self.subTest(length=len(changed)), self.assertRaises(ValueError):
                inspect(changed)


@unittest.skipUnless((REFERENCE/'AnalogFull.face').exists(), 'set MINIMAL_ANALOG_DIR to run the byte-exact reference test')
class PublicReferenceTests(unittest.TestCase):
    def test_exact_public_compiler_output(self):
        original = (REFERENCE/'AnalogFull.face').read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), REFERENCE_SHA)
        rebuilt = pack.compile_project(REFERENCE/'AnalogFull.fprj')
        self.assertEqual(len(rebuilt), 1094548)
        self.assertEqual(rebuilt, original)
        meta = inspect(original)
        self.assertEqual(meta['flags'], 4)
        self.assertEqual([len(f['components']) for f in meta['faces']], [8, 7])
        self.assertEqual([r['frames'] for r in meta['faces'][0]['resources']], [1,1,1,1,1,7,10,101])


if __name__ == '__main__':
    unittest.main()
