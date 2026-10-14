#!/usr/bin/env python3
"""Offline port of GB XiaomiFWHelper.parseAsWatchface + Band 9 size gate.
SPDX-License-Identifier: MIT
This is NOT Android execution, a signature check, or a device install test.
Bounds checking is intentionally stricter than the Java parser.
"""
import argparse
import json
from pathlib import Path
import re
import struct

LOCALES = ('en_US zh_CN zh_TW ja_JP es_ES fr_FR de_DE ru_RU pt_BR pt_PT it_IT '
           'ko_KR tr_TR nl_NL th_TH sv_SE da_DK vi_VN nb_NO pl_PL fi_FI in_ID '
           'el_GR ro_RO cs_CZ uk_UA hu_HU sk_SK ar_EG iw_IL zh_HK').split()


def parse_as_watchface(data, locale='en_US'):
    if len(data) < 168 or data[:2] != b'\x5a\xa5':
        raise ValueError('File header not a v2 watchface')

    def cstring(offset):
        end = data.find(b'\0', offset)
        if end < 0:
            raise ValueError(f'Missing NUL terminator at {offset:#x}')
        return data[offset:end].decode('utf-8', errors='replace')

    face_id = cstring(0x28)
    if not re.fullmatch(r'[0-9]+', face_id):
        raise ValueError('Id not a number')
    if data[0x68:0x6c] != b'\xff'*4:
        name = cstring(0x68)
    else:
        name = ''
        offset, size = struct.unpack_from('<II', data, 0x74)
        if size > 8 and offset + size <= len(data):
            bitmap, = struct.unpack_from('<Q', data, offset)
            bits = [i for i in range(64) if bitmap & (1 << i)]
            start = offset + 8 + 4*len(bits)
            if start <= offset + size:
                lengths = struct.unpack_from('<' + 'I'*len(bits), data, offset+8)
                candidates = [i for i in bits if i < len(LOCALES)]
                exact = [i for i in candidates if LOCALES[i] == locale]
                language = [i for i in candidates if LOCALES[i].split('_')[0] == locale.split('_')[0]]
                selected = exact[:1] or language[-1:] or candidates[:1]
                if selected:
                    j = bits.index(selected[0])
                    pos = start + sum(lengths[:j])
                    if pos + lengths[j] <= offset + size:
                        name = data[pos:pos+lengths[j]].decode('utf-8', errors='replace')
    preview, = struct.unpack_from('<I', data, 0x20)
    dimensions = None
    if preview > 0 and preview + 12 <= len(data):
        dimensions = struct.unpack_from('<HH', data, preview+4)
    screen = (192, 490)
    if dimensions == screen:
        compatibility = 'resolution_matches'
    elif dimensions is None:
        compatibility = 'unknown'  # Java permits missing previews; not an installation recommendation.
    else:
        w, h = dimensions
        if not w or not h or w > 192 or h > 490 or abs((w/h)/(192/490)-1) > .02:
            raise ValueError('Preview aspect ratio incompatible with Band 9')
        compatibility = 'aspect_ratio_matches'
    return {'gb_parse': 'PASS', 'id': face_id, 'name': name,
            'preview': list(dimensions) if dimensions else None,
            'band9_size_gate': compatibility,
            'device_installation': 'NOT_TESTED'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('face', type=Path)
    ap.add_argument('--locale', default='en_US')
    args = ap.parse_args()
    try:
        print(json.dumps(parse_as_watchface(args.face.read_bytes(), args.locale), ensure_ascii=False))
    except (ValueError, OSError, struct.error) as exc:
        ap.exit(2, f'FAIL: {exc}\n')


if __name__ == '__main__':
    main()
