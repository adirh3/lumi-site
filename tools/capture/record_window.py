"""Records a window's client area with PrintWindow (works while the window is behind others) until a stop
file appears. Frames are JPEGs named by elapsed milliseconds.

usage: python tools/capture/record_window.py <hwnd> <out_dir> <stop_file> [max_seconds] [fps]
"""
import ctypes
import os
import queue
import sys
import threading
import time
from ctypes import wintypes

from PIL import Image

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


def main():
    hwnd = int(sys.argv[1])
    out = sys.argv[2]
    stop = sys.argv[3]
    max_seconds = float(sys.argv[4]) if len(sys.argv) > 4 else 600
    interval = 1.0 / float(sys.argv[5]) if len(sys.argv) > 5 else 0.1
    os.makedirs(out, exist_ok=True)

    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    client = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(client))
    origin = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))
    ox, oy = origin.x - rect.left, origin.y - rect.top
    cw, ch = client.right, client.bottom

    screen = user32.GetDC(0)
    memdc = gdi32.CreateCompatibleDC(screen)
    bitmap = gdi32.CreateCompatibleBitmap(screen, w, h)
    gdi32.SelectObject(memdc, bitmap)
    info = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buffer = ctypes.create_string_buffer(w * h * 4)

    frames = queue.Queue(maxsize=256)

    def writer():
        while True:
            item = frames.get()
            if item is None:
                return
            stamp, raw = item
            image = Image.frombuffer("RGBX", (w, h), raw, "raw", "BGRX", 0, 1)
            image.crop((ox, oy, ox + cw, oy + ch)).convert("RGB").save(
                os.path.join(out, f"{stamp:07d}.jpg"), quality=94, subsampling=0)

    workers = [threading.Thread(target=writer, daemon=True) for _ in range(6)]
    for worker in workers:
        worker.start()

    start = time.perf_counter()
    count = 0
    while not os.path.exists(stop) and time.perf_counter() - start < max_seconds:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 4)
            user32.SetWindowPos(hwnd, -1, rect.left, rect.top, w + 1, h, 0x0010); time.sleep(0.4); user32.SetWindowPos(hwnd, -1, rect.left, rect.top, w, h, 0x0010)
            time.sleep(0.3)
            continue
        stamp = int((time.perf_counter() - start) * 1000)
        user32.PrintWindow(hwnd, memdc, 2)
        gdi32.GetDIBits(memdc, bitmap, 0, h, buffer, ctypes.byref(info), 0)
        frames.put((stamp, bytes(buffer.raw)))
        count += 1
        elapsed = time.perf_counter() - start - stamp / 1000
        time.sleep(max(0.0, interval - elapsed))
    for _ in workers:
        frames.put(None)
    for worker in workers:
        worker.join()
    seconds = time.perf_counter() - start
    print(f"{count} frames in {seconds:.1f}s ({count / seconds:.1f} fps), client {cw}x{ch}")


if __name__ == "__main__":
    main()
