# imghdr.py
import os

def what(file, h=None):
    """Determine the type of an image file."""
    if h is None:
        with open(file, 'rb') as f:
            h = f.read(32)
    for tf in tests:
        res = tf(h, file)
        if res:
            return res
    return None

def test_jpeg(h, f):
    """JPEG data in JFIF or Exif format"""
    if h[6:10] in (b'JFIF', b'Exif'):
        return 'jpeg'
    elif h[:4] == b'\xff\xd8\xff\xdb':
        return 'jpeg'

def test_png(h, f):
    if h.startswith(b'\211PNG\r\n\032\n'):
        return 'png'

def test_gif(h, f):
    """GIF ('87 and '89 variants)"""
    if h[:6] in (b'GIF87a', b'GIF89a'):
        return 'gif'

def test_tiff(h, f):
    """TIFF (can be in Little or Big endian format)"""
    if h[:2] in (b'MM', b'II'):
        return 'tiff'

def test_bmp(h, f):
    if h.startswith(b'BM'):
        return 'bmp'

tests = [
    test_jpeg,
    test_png,
    test_gif,
    test_tiff,
    test_bmp,
]