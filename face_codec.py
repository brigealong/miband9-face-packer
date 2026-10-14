"""Band 9 RGB565+A / RLE v10 codec. Independent Python implementation.
SPDX-License-Identifier: MIT
No target assembly is loaded or executed.
"""
from pathlib import Path
import struct
from PIL import Image


def rgb565a(image):
    """Row-major RGB565 little endian followed by straight 8-bit alpha.

    Deliberately use floor(channel * max / 255), not channel >> shift:
    that distinction is observable in the reference compiler.
    """
    out = bytearray()
    rgba = image.convert('RGBA')
    pixels = rgba.get_flattened_data() if hasattr(rgba, 'get_flattened_data') else rgba.getdata()
    for r, g, b, a in pixels:
        value = (r * 31 // 255 << 11) | (g * 63 // 255 << 5) | (b * 31 // 255)
        out.extend(struct.pack('<HB', value, a))
    return bytes(out)


def encode_rle(raw):
    if not raw or len(raw) % 3:
        raise ValueError('RLE input must contain whole RGB565+A pixels')
    out = bytearray()
    i = 0
    while i < len(raw):
        pixel = raw[i:i+3]
        count = 1
        while count < 127 and raw[i+3*count:i+3*count+3] == pixel:
            count += 1
        out.append(0x81 if count == 1 else count)
        out.extend(pixel)
        i += count * 3
    return bytes(out)


def decode_frame(frame, pixel_count):
    if len(frame) < 8 or frame[:4] != bytes.fromhex('e021a55a'):
        raise ValueError('Unsupported or truncated Band 9 RLE frame')
    param, = struct.unpack_from('<I', frame, 4)
    if param & 15 != 3 or param >> 4 != pixel_count * 3:
        raise ValueError('RLE declared size/record width mismatch')
    out = bytearray()
    i = 8
    while i < len(frame):
        tag = frame[i]
        i += 1
        count = tag & 127
        if not count:
            raise ValueError('Zero-length RLE run')
        size = count * 3 if tag & 128 else 3
        if i + size > len(frame):
            raise ValueError('Truncated RLE packet')
        block = frame[i:i+size]
        out.extend(block if tag & 128 else block * count)
        i += size
        if len(out) > pixel_count * 3:
            raise ValueError('RLE output exceeds dimensions')
    if len(out) != pixel_count * 3:
        raise ValueError('RLE output shorter than dimensions')
    return bytes(out)


def load_png(path):
    with Image.open(path) as im:
        if im.format != 'PNG':
            raise ValueError(f'Only PNG input supported: {path}')
        if not (0 < im.width <= 192 and 0 < im.height <= 490):
            raise ValueError(f'Image outside Band 9 dimensions: {path}')
        if im.mode not in ('1', 'L', 'LA', 'P', 'RGB', 'RGBA'):
            raise ValueError(f'Unsupported PNG mode {im.mode}: {path}')
        return im.convert('RGBA')


def frame_for(image):
    raw = rgb565a(image)
    return bytes.fromhex('e021a55a') + struct.pack('<I', len(raw) << 4 | 3) + encode_rle(raw)


def image_resource(paths, is_list=False):
    images = [load_png(Path(p)) for p in paths]
    if not images or len(images) > 255:
        raise ValueError('Image list must contain 1..255 frames')
    if len({im.size for im in images}) != 1:
        raise ValueError('All frames in an image list must have identical dimensions')
    w, h = images[0].size
    frames = [frame_for(im) for im in images]
    if is_list:
        return (struct.pack('<BBBBHHI', 6, len(images), 4, 0, w, h, sum(map(len, frames)))
                + struct.pack('<' + 'I' * len(frames), *map(len, frames)) + b''.join(frames))
    if len(frames) != 1:
        raise ValueError('A single image resource needs exactly one frame')
    return struct.pack('<BBBBHHI', 6, 4, 0, 0, w, h, len(frames[0])) + frames[0]


def resource_frames(resource, is_list=False):
    if len(resource) < 12:
        raise ValueError('Truncated image resource')
    fmt, count, compression, reserved, w, h, size = struct.unpack_from('<BBBBHHI', resource)
    if not (0 < w <= 192 and 0 < h <= 490):
        raise ValueError('Invalid image dimensions')
    if fmt != 6 or reserved != 0:
        raise ValueError('Unsupported image pixel format')
    if is_list:
        if compression != 4 or count == 0 or 12 + 4*count > len(resource):
            raise ValueError('Invalid image list header')
        lengths = struct.unpack_from('<' + 'I'*count, resource, 12)
        start = 12 + 4 * count
        if sum(lengths) != size or start + size != len(resource):
            raise ValueError('Image list byte lengths disagree')
    else:
        if count != 4 or compression != 0 or size + 12 != len(resource):
            raise ValueError('Invalid single-image header/size')
        lengths, start = [size], 12
    decoded = []
    for length in lengths:
        decoded.append(decode_frame(resource[start:start+length], w*h))
        start += length
    return w, h, decoded
