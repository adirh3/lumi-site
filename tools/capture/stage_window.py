"""Parks a window so only a thin sliver shows at the right edge of the rightmost monitor, topmost and never
activated: it keeps rendering at full size without covering anything, so record_window.py can capture it
while you keep working. 'park' moves it back onto that monitor at the bottom of the window stack. Both set
the window's client area to the given size (default 1980x1290, the size Lumi is captured at).

usage: python tools/capture/stage_window.py <hwnd> sliver|park [client_width client_height]
Lumi's client area must be 1980x1290 on a 100% (96 DPI) monitor. Windows only.
"""
import ctypes
import sys
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
# HWND_TOPMOST is -1: without pointer-sized argtypes it is truncated and the call silently does nothing.
user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
SWP_NOACTIVATE = 0x0010
HWND_TOPMOST, HWND_BOTTOM, HWND_NOTOPMOST = -1, 1, -2


def monitors():
    found = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(wintypes.RECT), ctypes.c_ssize_t)

    def callback(_monitor, _dc, rect, _data):
        r = rect.contents
        found.append((r.left, r.top, r.right, r.bottom))
        return 1

    user32.EnumDisplayMonitors(None, None, proc(callback), 0)
    return found


hwnd = int(sys.argv[1])
mode = sys.argv[2]
cw, ch = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (1980, 1290)
left, top, right, _ = max(monitors(), key=lambda m: m[2])

if user32.IsIconic(hwnd):
    user32.ShowWindow(hwnd, 4)
    time.sleep(0.5)
# The outer size is the client size plus the window's own frame.
outer, client = wintypes.RECT(), wintypes.RECT()
user32.GetWindowRect(hwnd, ctypes.byref(outer))
user32.GetClientRect(hwnd, ctypes.byref(client))
W = cw + (outer.right - outer.left) - client.right
H = ch + (outer.bottom - outer.top) - client.bottom
if mode == "sliver":
    # Resize by a pixel and back so the window re-lays out at exactly the requested client size.
    for width in (W + 1, W):
        user32.SetWindowPos(hwnd, HWND_TOPMOST, right - 12, top, width, H, SWP_NOACTIVATE)
        time.sleep(0.5)
else:
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, left + 60, top, W, H, SWP_NOACTIVATE)
    user32.SetWindowPos(hwnd, HWND_BOTTOM, left + 60, top, W, H, SWP_NOACTIVATE)
client = wintypes.RECT()
user32.GetClientRect(hwnd, ctypes.byref(client))
print(mode, "dpi", user32.GetDpiForWindow(hwnd), "client", f"{client.right}x{client.bottom}")
if (client.right, client.bottom) != (cw, ch):
    print(f"warning: the client area is {client.right}x{client.bottom}, not {cw}x{ch}; run it again before recording")
