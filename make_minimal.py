#!/usr/bin/env python3
"""Generate original Band 9 probe assets (time, 2031, 5031).
SPDX-License-Identifier: MIT
"""
from pathlib import Path
import argparse
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

SEGMENTS = ['ab cdef'.replace(' ', ''), 'bc', 'abdeg', 'abcdg', 'bcfg',
            'acdfg', 'acdefg', 'abc', 'abcdefg', 'abcdfg']


def digit(value, width, height):
    im = Image.new('RGBA', (width, height))
    draw = ImageDraw.Draw(im)
    t, m, mid = max(2, width//7), 2, height//2
    bars = {'a': (m+t,m,width-m-t,m+t), 'd': (m+t,height-m-t,width-m-t,height-m),
            'g': (m+t,mid-t//2,width-m-t,mid+t//2),
            'f': (m,m+t,m+t,mid-t), 'b': (width-m-t,m+t,width-m,mid-t),
            'e': (m,mid+t,m+t,height-m-t), 'c': (width-m-t,mid+t,width-m,height-m-t)}
    for seg in ('g' if value == '-' else SEGMENTS[int(value)]):
        draw.rectangle(bars[seg], fill='white')
    return im


def generate(out):
    images = out / 'images'
    images.mkdir(parents=True, exist_ok=True)
    bg = Image.new('RGBA', (192, 490), (0, 0, 0, 255))
    draw = ImageDraw.Draw(bg)
    font = ImageFont.load_default(size=18)
    for y, text in ((146, 'TEMP / 5h %'), (302, 'AQI / reset min')):
        draw.text((96,y), text, font=font, anchor='mt', fill='white')
    draw.text((96,75), ':', font=ImageFont.load_default(size=36), anchor='mm', fill='white')
    bg.save(images / 'background.png')
    root = ET.Element('FaceProject', DeviceType='366', Id='167210065')
    screen = ET.SubElement(root, 'Screen', Title='Usage Probe', Bitmap='preview.png')
    ET.SubElement(screen, 'Widget', Shape='30', Name='background', Bitmap='background.png',
                  X='0', Y='0', Width='192', Height='490', Alpha='255', Visible_Src='0')
    preview = bg.copy()
    for name, source, width, height, digits, x, y, blanking, demo in (
        ('hours', '0811', 28, 52, 2, 27, 49, 0, '12'),
        ('minutes', '1011', 28, 52, 2, 109, 49, 0, '34'),
        ('temperature', '2031', 44, 76, 3, 30, 184, 1, '57'),
        ('aqi', '5031', 44, 76, 3, 30, 340, 1, '138'),
    ):
        names = []
        for i in range(11):
            filename = f'{name}_{i}.png'
            digit(str(i) if i < 10 else '-', width, height).save(images / filename)
            names.append(filename)
        ET.SubElement(screen, 'Widget', Shape='32', Name=name, X=str(x), Y=str(y),
                      Width=str(width*digits), Height=str(height), Alpha='255', Visible_Src='0',
                      BitmapList='|'.join(names), Value_Src=source, Digits=str(digits),
                      Alignment='1', Blanking=str(blanking), Spacing='0')
        start = x + (digits-len(demo))*width//2
        for j, value in enumerate(demo):
            preview.alpha_composite(digit(value, width, height), (start+j*width, y))
    preview.save(images / 'preview.png')
    ET.indent(root)
    ET.ElementTree(root).write(out / 'UsageProbe.fprj', encoding='utf-8', xml_declaration=True)
    print(f'OK generated {out}: time 0811/1011, temperature 2031, AQI 5031')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('directory', nargs='?', type=Path, default=Path(__file__).parent/'samples'/'minimal')
    generate(ap.parse_args().directory)
