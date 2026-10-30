"""Scrolls a window's content smoothly by posting small WM_MOUSEWHEEL steps to it at a point in its client
area, like a touchpad: no focus change, no real pointer movement.

usage: python tools/capture/wheel.py <hwnd> <client_x> <client_y> <total_delta> <seconds> [hz]
       total_delta > 0 scrolls up (towards older content); 120 = one wheel notch.
"""
import ctypes
import math
import sys
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM, wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
result = ctypes.c_size_t()

hwnd = int(sys.argv[1])
cx, cy = int(sys.argv[2]), int(sys.argv[3])
total = float(sys.argv[4])
seconds = float(sys.argv[5])
hz = float(sys.argv[6]) if len(sys.argv) > 6 else 120.0

pt = wintypes.POINT(cx, cy)
user32.ClientToScreen(hwnd, ctypes.byref(pt))
lparam = ((pt.y & 0xFFFF) << 16) | (pt.x & 0xFFFF)

steps = max(1, round(seconds * hz))
# Ease in and out: the cumulative distance follows a smoothstep over the gesture.
done = 0
sent = 0
start = time.perf_counter()
for i in range(1, steps + 1):
    x = i / steps
    target = total * (x * x * (3 - 2 * x))
    delta = int(round(target - done))
    if delta:
        # Sent, not posted: a posted wheel message does not wake an idle Avalonia message loop.
        user32.SendMessageTimeoutW(hwnd, 0x020A, (delta & 0xFFFF) << 16, lparam, 0x0002, 1000, ctypes.byref(result))
        done += delta
        sent += 1
    wait = start + i / hz - time.perf_counter()
    if wait > 0:
        time.sleep(wait)
print(f"posted {sent} wheel steps, total {done}, at screen {pt.x},{pt.y}")
