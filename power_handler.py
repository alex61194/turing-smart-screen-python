#!/usr/bin/env python
# -*- coding: utf-8 -*-
import subprocess
import os
import sys
import time
import ctypes
from ctypes import wintypes, Structure, sizeof, byref
from pathlib import Path

MAIN_DIR = Path(__file__).resolve().parent
PYTHON_PATH = sys.executable
MAIN_SCRIPT = str(MAIN_DIR / "main.py")
LOG_FILE = str(MAIN_DIR / "power_handler.log")
SHUTDOWN_SIGNAL_FILE = str(MAIN_DIR / ".shutdown_signal")

WM_POWERBROADCAST = 0x0218
WM_QUERYENDSESSION = 0x0011
WM_ENDSESSION = 0x0016
PBT_APMSUSPEND = 0x0004
PBT_APMRESUMEAUTOMATIC = 0x0012
PBT_APMRESUMESUSPEND = 0x0007
PBT_APMRESUMECRITICAL = 0x0006

WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8

monitor_proc = None


def log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass


def signal_shutdown():
    try:
        with open(SHUTDOWN_SIGNAL_FILE, "w") as f:
            f.write("shutdown")
        log("Shutdown signal file created")
    except Exception as e:
        log(f"Failed to create shutdown signal: {e}")


def clear_shutdown_signal():
    try:
        if os.path.exists(SHUTDOWN_SIGNAL_FILE):
            os.remove(SHUTDOWN_SIGNAL_FILE)
    except:
        pass


def start_monitor():
    global monitor_proc
    if monitor_proc and monitor_proc.poll() is None:
        log("Monitor already running")
        return
    clear_shutdown_signal()
    monitor_proc = subprocess.Popen(
        [PYTHON_PATH, "-u", MAIN_SCRIPT],
        creationflags=0x08000000,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    log(f"Monitor started PID={monitor_proc.pid}")


def stop_monitor_graceful():
    global monitor_proc
    if not monitor_proc or monitor_proc.poll() is not None:
        monitor_proc = None
        return
    pid = monitor_proc.pid
    log(f"Signaling graceful shutdown to PID={pid}")
    signal_shutdown()
    for i in range(20):
        time.sleep(0.5)
        if monitor_proc.poll() is not None:
            log(f"Monitor exited gracefully PID={pid}")
            monitor_proc = None
            return
    log(f"Graceful shutdown timeout, force killing PID={pid}")
    try:
        subprocess.run(["taskkill", "/f", "/pid", str(pid)],
                       capture_output=True, timeout=5)
    except:
        pass
    try:
        monitor_proc.wait(timeout=3)
    except:
        pass
    clear_shutdown_signal()
    log(f"Monitor killed PID={pid}")
    monitor_proc = None


def stop_monitor_force():
    global monitor_proc
    if not monitor_proc or monitor_proc.poll() is not None:
        monitor_proc = None
        return
    pid = monitor_proc.pid
    try:
        subprocess.run(["taskkill", "/f", "/pid", str(pid)],
                       capture_output=True, timeout=5)
    except:
        pass
    try:
        monitor_proc.wait(timeout=3)
    except:
        pass
    clear_shutdown_signal()
    log(f"Monitor force killed PID={pid}")
    monitor_proc = None


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
wtsapi32 = ctypes.windll.wtsapi32


class WNDCLASSEXW(Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HANDLE),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HANDLE),
    ]


WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long, wintypes.HWND, wintypes.UINT,
    wintypes.WPARAM, wintypes.LPARAM)


def wnd_proc(hwnd, msg, wparam, lparam):
    if msg == WM_WTSSESSION_CHANGE:
        if lparam == WTS_SESSION_LOCK:
            log("SESSION LOCKED - stopping monitor")
            stop_monitor_graceful()
        elif lparam == WTS_SESSION_UNLOCK:
            log("SESSION UNLOCKED - starting monitor")
            time.sleep(2)
            start_monitor()
        return 0
    if msg == WM_POWERBROADCAST:
        if wparam == PBT_APMSUSPEND:
            log("SYSTEM SUSPENDING - stopping monitor")
            stop_monitor_graceful()
            return 1
        elif wparam in (PBT_APMRESUMEAUTOMATIC,
                        PBT_APMRESUMESUSPEND,
                        PBT_APMRESUMECRITICAL):
            log("SYSTEM RESUMING - starting monitor")
            clear_shutdown_signal()
            time.sleep(3)
            start_monitor()
            return 1
        return 1
    if msg == WM_QUERYENDSESSION:
        log("SYSTEM SHUTTING DOWN - stopping monitor")
        stop_monitor_graceful()
        return 1
    if msg == WM_ENDSESSION:
        if wparam:
            log("System shutdown confirmed")
        else:
            log("System shutdown cancelled")
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def main():
    log("=== Power handler starting ===")
    clear_shutdown_signal()
    hInstance = kernel32.GetModuleHandleW(None)
    className = "TuringSleepHandler8"

    wc = WNDCLASSEXW()
    wc.cbSize = sizeof(WNDCLASSEXW)
    wc.style = 0
    wc.lpfnWndProc = ctypes.cast(WNDPROC(wnd_proc), ctypes.c_void_p).value
    wc.cbClsExtra = 0
    wc.cbWndExtra = 0
    wc.hInstance = hInstance
    wc.hIcon = None
    wc.hCursor = None
    wc.hbrBackground = None
    wc.lpszMenuName = None
    wc.lpszClassName = className
    wc.hIconSm = None

    atom = user32.RegisterClassExW(byref(wc))
    if not atom:
        log(f"RegisterClassExW failed: {kernel32.GetLastError()}")
        return

    hwnd = user32.CreateWindowExW(
        0, className, "TuringSleep",
        0, -32000, -32000, 1, 1,
        None, None, hInstance, None
    )
    if not hwnd:
        log(f"CreateWindowExW failed: {kernel32.GetLastError()}")
        return

    result = wtsapi32.WTSRegisterSessionNotification(hwnd, 0)
    log(f"WTSRegisterSessionNotification: {result}")

    user32.ShowWindow(hwnd, 0)
    user32.UpdateWindow(hwnd)
    log(f"Window created hwnd={hwnd:#x}")

    start_monitor()
    log("Entering message loop")

    msg = wintypes.MSG()
    while (user32.GetMessageW(byref(msg), None, 0, 0)) != 0:
        user32.TranslateMessage(byref(msg))
        user32.DispatchMessageW(byref(msg))

    wtsapi32.WTSUnRegisterSessionNotification(hwnd)
    log("Power handler exiting")


if __name__ == "__main__":
    main()
