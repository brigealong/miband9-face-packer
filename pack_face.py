#!/usr/bin/env python3
"""Offline Band 9 .fprj -> v2 .face compiler; SPDX-License-Identifier: MIT.

Implements static images, indexed image lists, digital numbers, analog hands,
AOD and multiple faces. Unknown shapes and name-driven actions fail closed.
No shell commands, target execution, network or device access.
"""
import argparse
from dataclasses import dataclass, field
from pathlib import Path
import re
import struct
import sys
import xml.etree.ElementTree as ET
from face_codec import image_resource, load_png


@dataclass
class Item:
    kind: str
    attrs: dict
    paths: tuple = ()
    values: tuple = ()
    source: str = ''
    pivot: tuple = (0, 0)
    period: int = 0
    maximum: int = 0
    image_id: int = 0
    target_id: int = 0
    element_pos: int = 0
    widget_pos: int = 0


@dataclass
class Face:
    path: Path
    title: str
    preview: str
    items: list
    tables: dict = field(default_factory=dict)
    lists: dict = field(default_factory=dict)


def integer(attrs, key, default=0):
    return int(attrs.get(key, default))


def data_source(text):
    if not re.fullmatch(r'[0-9A-Fa-f]{1,8}', text):
        raise ValueError(f'Invalid hex data source: {text!r}')
    # The compiler accepts its legacy prefix+low-word notation too.
    value = int(text[-4:], 16) + (int(text[:-4], 16) if len(text) > 4 else 0)
    return (value & 0xffff).to_bytes(2, 'big')


def safe_image(base, name):
    # .fprj stores Windows separators. Do not allow paths outside images/.
    if not name:
        raise ValueError('Missing image filename')
    path = (base / name.replace('\\', '/')).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError(f'Image escapes images directory: {name}')
    if path.suffix.lower() != '.png' or not path.is_file():
        raise ValueError(f'Missing PNG: {path}')
    return path


def parse_project(path, main_root):
    xml_bytes = path.read_bytes()
    if b'<!DOCTYPE' in xml_bytes.upper() or b'<!ENTITY' in xml_bytes.upper():
        raise ValueError('DTD/entities are not supported')
    root = ET.fromstring(xml_bytes)
    if root.tag != 'FaceProject' or root.get('DeviceType') != '366':
        raise ValueError(f'Only Band 9 DeviceType=366 is supported: {path}')
    screens = root.findall('Screen')
    if len(screens) != 1:
        raise ValueError('Exactly one Screen required per .fprj')
    screen = screens[0]
    if any(w.tag != 'Widget' for w in screen):
        raise ValueError('Unsupported Screen child')
    items = []
    for node in screen:
        if len(node):
            raise ValueError('Nested widgets/containers are not implemented')
        a = dict(node.attrib)
        name = a.get('Name', '').lower()
        if (name.startswith(('anim_', 'btn_', 'app_', 'lineprogress_'))
                or any(s in name for s in ('_ref[', '_color[', '_smooth', '_nocompress'))):
            raise ValueError(f'Unsupported name-driven feature: {name}')
        if integer(a, 'Alpha', 255) != 255 or integer(a, 'Visible_Src') != 0:
            raise ValueError('Only Alpha=255 and Visible_Src=0 are supported')
        x, y = integer(a, 'X'), integer(a, 'Y')
        if not (-32768 <= x <= 32767 and -32768 <= y <= 32767):
            raise ValueError('Coordinates exceed signed 16-bit range')
        shape = integer(a, 'Shape')
        base = path.parent / 'images'
        if shape == 30:
            items.append(Item('image', a, (safe_image(base, a.get('Bitmap')),)))
        elif shape in (31, 32):
            entries = a.get('BitmapList', '').split('|')
            values, paths = [], []
            for entry in entries:
                if shape == 31:
                    match = re.fullmatch(r'\((-?\d+)\):(.+)', entry)
                    if not match:
                        raise ValueError('Image lists require (index):filename entries')
                    values.append(int(match[1]))
                    entry = match[2]
                paths.append(safe_image(base, entry))
            if not 1 <= len(paths) <= 255:
                raise ValueError('Lists must have 1..255 frames')
            if shape == 32:
                if not 10 <= len(paths) <= 12:
                    raise ValueError('Numeric list needs digits 0..9, optional minus and dot')
                if not 1 <= integer(a, 'Digits') <= 40:
                    raise ValueError('Digits must be in 1..40')
                if integer(a, 'Alignment') not in (0, 1, 2):
                    raise ValueError('Alignment must be 0, 1 or 2')
                if integer(a, 'Blanking') not in (0, 1) or not 0 <= integer(a, 'Spacing') <= 255:
                    raise ValueError('Invalid Blanking or Spacing')
            src = a.get('Value_Src' if shape == 32 else 'Index_Src', '')
            data_source(src)
            items.append(Item('number' if shape == 32 else 'list', a, tuple(paths), tuple(values), src))
        elif shape == 27:
            for hand, image_attr, source, period, maximum in (
                ('Hour', 'HourHand_ImageName', '0811', 24, 7200),
                ('Minute', 'MinuteHand_Image', '1011', 60, 3600),
                ('Second', 'SecondHand_Image', '1811', 60, 3600),
            ):
                image = a.get(image_attr)
                if not image:
                    continue
                # Compatibility with compile.exe 4.22: AOD second hand uses
                # main images/, unlike hour/minute. No fallback is concealed.
                hand_base = main_root / 'images' if hand == 'Second' else base
                pivot = (integer(a, hand + 'Image_rotate_xc'), integer(a, hand + 'Image_rotate_yc'))
                items.append(Item('hand', a, (safe_image(hand_base, image),), source=source,
                                  pivot=pivot, period=period, maximum=maximum))
        else:
            raise ValueError(f'Unsupported widget Shape={shape}: {name}')
    if not items:
        raise ValueError('Screen must contain at least one supported widget')
    return Face(path, screen.get('Title', ''), screen.get('Bitmap', ''), items)


def find_projects(project):
    if project.is_dir():
        paths = sorted(project.glob('*.fprj'))
        if not paths:
            raise ValueError('No .fprj in project directory')
        main = paths[0]
    else:
        main = project
        paths = sorted(main.parent.glob('*.fprj'))
    faces = [main]
    aod_dir = main.parent / 'AOD'
    has_aod = (aod_dir / 'images').is_dir()
    if has_aod:
        aods = list(aod_dir.glob('*.fprj'))
        if len(aods) != 1:
            raise ValueError('AOD/images exists but not exactly one AOD .fprj')
        faces.extend(aods)
    faces.extend(p for p in paths if p != main)
    if len(faces) > 255:
        raise ValueError('Too many faces')
    return main, faces, has_aod


def compile_project(project, face_id='167210065'):
    if not re.fullmatch(r'[0-9]{9}', face_id):
        raise ValueError('ID must be exactly nine ASCII digits')
    main, projects, has_aod = find_projects(Path(project).resolve())
    faces = [parse_project(p, main.parent) for p in projects]
    title = faces[0].title.encode('utf-8')
    if not title or b'\0' in title or len(title) > 63:
        raise ValueError('Title must occupy 1..63 UTF-8 bytes, without NUL')
    data = bytearray(168 + 88 * len(faces))

    def u32(pos, value):
        struct.pack_into('<I', data, pos, value)

    def u16(pos, value):
        struct.pack_into('<H', data, pos, value & 0xffff)

    def allocate(payload):
        pos = len(data)
        data.extend(payload)
        data.extend(b'\0' * (-len(data) % 4))
        return pos

    def record(table, index, ident, pos, size):
        struct.pack_into('<IIII', data, table + 16*index, ident, 0, pos, size)

    data[:4] = bytes.fromhex('5aa53412')
    u32(16, 2048)
    data[28] = len(faces)
    data[30] = (4 if has_aod else 0) | (2 if len(faces) - int(has_aod) > 1 else 0)
    data[40:49] = face_id.encode('ascii')
    data[104:104+len(title)] = title
    # Reserve ALL face index tables before allocating any payload.
    for fi, face in enumerate(faces):
        h = 168 + fi * 88
        u32(h+4, 0xffffffff)
        face.lists = dict.fromkeys(i.paths for i in face.items if i.kind in ('number', 'list'))
        counts = {0: len(face.items), 2: sum(i.kind in ('image', 'hand') for i in face.items),
                  3: len(face.lists), 7: sum(i.kind != 'image' for i in face.items)}
        for kind in range(10):
            count = counts.get(kind, 0)
            pos = len(data)
            u32(h+8+8*kind, count)
            u32(h+12+8*kind, pos)
            face.tables[kind] = pos
            data.extend(b'\0' * count * 16)
    next_id = {2: 0, 3: 0, 7: 0}

    def ident(kind):
        index = next_id[kind]
        if index > 255:
            raise ValueError(f'Type {kind} resource count exceeds byte-sized reference indices')
        next_id[kind] += 1
        return kind << 24 | index

    for face in faces:
        for index, item in enumerate(face.items):
            item.element_pos = allocate(bytes(16))
            record(face.tables[0], index, index, item.element_pos, 16)
        index = 0
        for item in face.items:
            if item.kind == 'image':
                continue
            item.target_id = ident(7)
            size = {'number': 20, 'list': 16 + 4*len(item.values), 'hand': 32}[item.kind]
            item.widget_pos = allocate(bytes(size))
            record(face.tables[7], index, item.target_id, item.widget_pos, size)
            index += 1
        index = 0
        for item in face.items:
            if item.kind not in ('image', 'hand'):
                continue
            item.image_id = ident(2)
            payload = image_resource(item.paths)
            pos = allocate(payload)
            record(face.tables[2], index, item.image_id, pos, len(payload))
            index += 1
        index = 0
        for item in face.items:
            if item.kind not in ('number', 'list'):
                continue
            if face.lists[item.paths] is None:
                list_id = ident(3)
                face.lists[item.paths] = list_id
                payload = image_resource(item.paths, is_list=True)
                pos = allocate(payload)
                record(face.tables[3], index, list_id, pos, len(payload))
                index += 1
            item.image_id = face.lists[item.paths]
        for item in face.items:
            a = item.attrs
            x, y = integer(a, 'X'), integer(a, 'Y')
            if item.kind == 'number':
                glyph_width = load_png(item.paths[0]).width
                alignment = integer(a, 'Alignment')
                extent = glyph_width * integer(a, 'Digits')
                x += extent // 2 if alignment == 1 else (extent if alignment == 2 else 0)
            elif item.kind == 'hand':
                x += integer(a, 'Width') // 2 - item.pivot[0]
                y += integer(a, 'Height') // 2 - item.pivot[1]
            if not (-32768 <= x <= 32767 and -32768 <= y <= 32767):
                raise ValueError('Adjusted anchor exceeds signed 16-bit coordinates')
            e = item.element_pos
            u32(e, item.image_id if item.kind == 'image' else item.target_id)
            u16(e+4, x)
            u16(e+6, y)
            if item.kind == 'image':
                continue
            w = item.widget_pos
            data[w:w+2] = data_source(item.source)
            u32(w+8, item.image_id)
            angle = re.search(r'_angle\[(\d+)\]', a.get('Name', '').lower())
            if angle:
                value = int(angle[1])
                u16(w+14, value if 0 < value < 3600 else 0)
            if item.kind == 'number':
                data[w+2] = integer(a, 'Digits')
                align_bits = {0: 1, 1: 2, 2: 0}[integer(a, 'Alignment')]
                data[w+3] = 0x10 | (4 if integer(a, 'Blanking') == 0 else 0) | align_bits
                data[w+13] = integer(a, 'Spacing')
            elif item.kind == 'list':
                data[w+3] = 0x20
                # 4.22 emits a custom-value map even for sequential indices.
                u32(w+12, 512)
                for j, value in enumerate(item.values):
                    u32(w+16+4*j, value & 0xffffffff)
            else:
                data[w+3] = 0x30
                u16(w+6, 1000)
                data[w+17] = item.period
                u16(w+20, item.pivot[0])
                u16(w+22, item.pivot[1])
                u16(w+26, item.maximum)
    preview_path = safe_image(main.parent / 'images', faces[0].preview)
    preview = load_png(preview_path)
    if preview.size not in ((192, 490), (122, 310)):
        raise ValueError('Band 9 preview must be 192x490 or 122x310')
    preview_pos = allocate(image_resource((preview_path,)))
    u32(32, preview_pos)
    u32(168+4, preview_pos)
    return bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path, help='Directory or main .fprj (recommended for multi-face projects)')
    parser.add_argument('output', type=Path)
    parser.add_argument('--id', default='167210065', help='Nine numeric digits; default matches compile.exe')
    args = parser.parse_args()
    try:
        result = compile_project(args.project, args.id)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(result)
        print(f'OK {args.output}: {len(result)} bytes, id={args.id}, faces={result[28]}')
    except (ValueError, OSError, ET.ParseError) as exc:
        parser.exit(2, f'ERROR: {exc}\n')


if __name__ == '__main__':
    main()
