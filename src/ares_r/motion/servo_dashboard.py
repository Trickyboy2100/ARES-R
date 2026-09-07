"""Observe native JSON feedback without adding controller calls or servo threads.

Keyboard-stop design adapted from tmp/servo_left_driver.py; only the native
owner calls SDK abort/disable. A terminal key is a stop request, not an E-stop.
"""
import json
import math
import os
import select
import sys
import time
from contextlib import contextmanager


@contextmanager
def keyboard():
    saved=None
    try:
        if sys.stdin.isatty():
            import termios
            import tty
            fd=sys.stdin.fileno();saved=termios.tcgetattr(fd)
            tty.setcbreak(fd)  # retain Ctrl+C signals, unlike the experimental raw mode
        yield
    finally:
        if saved is not None: termios.tcsetattr(fd,termios.TCSADRAIN,saved)


def stop_key():
    if not sys.stdin.isatty(): return False
    if select.select([sys.stdin],[],[],0)[0]:
        value=os.read(sys.stdin.fileno(),1)
        return value in (b"q",b"Q",b" ",b"\x1b",b"\x03",b"")
    return False


def render(event, total, elapsed, phase):
    index=event.get("index",-1)+1
    q=event.get("actual_rad",[]);target=event.get("target_rad",[])
    tcp=event.get("tcp_mm_rad",[])
    lines=["ARES-R | RIGHT servo | %s | %s"%(phase,event.get("event","waiting for feedback")),
           "Progress %d/%d (%5.1f%%) | elapsed %.1fs"%(index,total,100*index/max(1,total),elapsed),
           "Actual J1..J6 deg: "+" ".join("%8.3f"%math.degrees(v) for v in q),
           "Target J1..J6 deg: "+" ".join("%8.3f"%math.degrees(v) for v in target),
           "Actual TCP (controller BASE, mm): "+" ".join("%9.2f"%v for v in tcp[:3]),
           "Previous-target following error: %.4f deg"%event.get("tracking_error_deg",0),
           "SPACE / q / Esc / Ctrl+C: STOP + exit | physical E-stop remains required"]
    return "\n".join(lines)


def monitor(child, log, trajectory, phase, timeout=150):
    start=time.monotonic();event={};last_draw=0;pending="";interactive=sys.stdout.isatty()
    interrupted=False
    try:
        with keyboard(),log.open() as reader:
            while True:
                chunk=reader.read()
                if chunk:
                    pending+=chunk
                    lines=pending.split("\n");pending=lines.pop()
                    for line in lines:
                        if line.startswith("{"):
                            parsed=json.loads(line)
                            event.update(parsed)
                now=time.monotonic()
                if now-last_draw> (.1 if interactive else 2):
                    output=render(event,len(trajectory["points"]),now-start,phase)
                    if interactive: print("\033[H\033[J"+output,flush=True)
                    else: print(output.splitlines()[0]+" | "+output.splitlines()[1],flush=True)
                    last_draw=now
                if child.poll() is not None: break
                if stop_key() or now-start>timeout: raise KeyboardInterrupt
                time.sleep(.025)
    except BaseException:
        # Also handle broken UI pipes/JSON/terminal errors: never abandon a sender.
        interrupted=True
        if child.poll() is None: child.terminate()
        try: child.wait(timeout=10)
        except Exception as exc:
            raise RuntimeError("native stop unconfirmed; physical E-stop required; log: %s"%log) from exc
        raise RuntimeError("execution stopped; no automatic return; inspect cleanup: %s"%log)
    finally:
        if not interrupted and interactive:
            print(render(event,len(trajectory["points"]),time.monotonic()-start,phase),flush=True)
    return child.returncode
