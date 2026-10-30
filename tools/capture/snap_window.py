"""Captures one frame of a window's client area with PrintWindow, like record_window.py.
usage: python tools/capture/snap_window.py <hwnd> <out_png> [max_width]"""
import ctypes, sys
from ctypes import wintypes
from PIL import Image
user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
class BMI(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]
hwnd = int(sys.argv[1])
r = wintypes.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(r)); w, h = r.right - r.left, r.bottom - r.top
c = wintypes.RECT(); user32.GetClientRect(hwnd, ctypes.byref(c)); o = wintypes.POINT(0, 0); user32.ClientToScreen(hwnd, ctypes.byref(o))
ox, oy = o.x - r.left, o.y - r.top
screen = user32.GetDC(0); mem = gdi32.CreateCompatibleDC(screen); bmp = gdi32.CreateCompatibleBitmap(screen, w, h); gdi32.SelectObject(mem, bmp)
user32.PrintWindow(hwnd, mem, 2)
buf = ctypes.create_string_buffer(w * h * 4); info = BMI(ctypes.sizeof(BMI), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(info), 0)
im = Image.frombuffer("RGBX", (w, h), buf.raw, "raw", "BGRX", 0, 1).crop((ox, oy, ox + c.right, oy + c.bottom)).convert("RGB")
full = im.size
if len(sys.argv) > 3 and im.width > int(sys.argv[3]):
    mw = int(sys.argv[3]); im = im.resize((mw, round(im.height * mw / im.width)), Image.LANCZOS)
im.save(sys.argv[2]); print(sys.argv[2], "client", full, "saved", im.size)
