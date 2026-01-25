from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
import time


TASK_NAME = "TimeCorrect"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))

def self_path() -> str:
    if is_frozen():
        return os.path.abspath(sys.executable)
    return os.path.abspath(__file__)


def elevate_self(script_path: str, extra_args: list[str]) -> int:
    """
    Re-run python elevated (UAC), ensuring the script path is absolute and working directory is set.
    """
    if is_frozen():
        args = ["--no-elevate"] + extra_args
        params = subprocess.list2cmdline(args)
        workdir = os.path.dirname(sys.executable) or None
        file_to_run = sys.executable
    else:
        args = [script_path, "--no-elevate"] + extra_args
        params = subprocess.list2cmdline(args)
        workdir = os.path.dirname(script_path) or None
        file_to_run = sys.executable

    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", file_to_run, params, workdir, 1)
    return 0 if rc > 32 else 1


def msgbox(text: str, title: str = "TimeCorrect") -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x00000010)
    except Exception:
        pass


def run(cmd: list[str], quiet: bool) -> int:
    creationflags = 0
    if is_frozen() or quiet:
        creationflags = CREATE_NO_WINDOW

    p = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        encoding="oem",
        errors="replace",
        creationflags=creationflags,
    )
    if (not quiet) and p.stdout:
        print(p.stdout.rstrip())
    if (not quiet) and p.stderr:
        print(p.stderr.rstrip(), file=sys.stderr)
    return p.returncode


def task_exists() -> bool:
    p = subprocess.run(
        ["schtasks", "/Query", "/TN", TASK_NAME],
        text=True,
        capture_output=True,
        encoding="oem",
        errors="replace",
        creationflags=CREATE_NO_WINDOW if is_frozen() else 0,
    )
    return p.returncode == 0


def install_autostart(ntp: str, delay_minutes: int, quiet: bool) -> int:
    dest_dir = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "TimeCorrect")
    os.makedirs(dest_dir, exist_ok=True)

    src = self_path()
    base = "TimeCorrect.exe" if is_frozen() else "TimeCorrect.py"
    dest = os.path.join(dest_dir, base)

    try:
        with open(src, "rb") as fsrc, open(dest, "wb") as fdst:
            fdst.write(fsrc.read())
    except OSError as e:
        if not quiet:
            print(f"ERROR: failed to copy to {dest}: {e}", file=sys.stderr)
        return 10

    delay = f"{delay_minutes:04d}:00".replace("0000", "0000")
    if delay_minutes < 0:
        delay_minutes = 0
    delay_arg = f"{delay_minutes:04d}:00"

    if is_frozen():
        tr = f"\"{dest}\" --quiet --ntp \"{ntp}\""
    else:
        tr = f"\"{sys.executable}\" \"{dest}\" --quiet --ntp \"{ntp}\""

    cmd = [
        "schtasks",
        "/Create",
        "/F",
        "/TN",
        TASK_NAME,
        "/SC",
        "ONSTART",
        "/DELAY",
        delay_arg,
        "/RL",
        "HIGHEST",
        "/RU",
        "SYSTEM",
        "/TR",
        tr,
    ]

    rc = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        encoding="oem",
        errors="replace",
        creationflags=CREATE_NO_WINDOW if (is_frozen() or quiet) else 0,
    ).returncode
    if rc == 0:
        if not quiet:
            print(f"Installed autostart task '{TASK_NAME}' (startup, SYSTEM).")
        return 0
    if not quiet:
        print("ERROR: failed to create scheduled task.", file=sys.stderr)
    return 11


def uninstall_autostart(quiet: bool) -> int:
    subprocess.run(
        ["schtasks", "/Delete", "/F", "/TN", TASK_NAME],
        text=True,
        capture_output=True,
        encoding="oem",
        errors="replace",
        creationflags=CREATE_NO_WINDOW if (is_frozen() or quiet) else 0,
    )
    dest_dir = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "TimeCorrect")
    try:
        if os.path.isdir(dest_dir):
            for name in os.listdir(dest_dir):
                try:
                    os.remove(os.path.join(dest_dir, name))
                except OSError:
                    pass
            try:
                os.rmdir(dest_dir)
            except OSError:
                pass
    except OSError:
        pass
    if not quiet:
        print(f"Removed autostart task '{TASK_NAME}' (if it existed).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ntp", default="pool.ntp.org", help="NTP server(s), separated by spaces")
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--delay", type=int, default=3, help="delay between retries (seconds)")
    ap.add_argument("--delay-minutes", type=int, default=1, help="autostart delay after boot (minutes)")
    ap.add_argument("--no-elevate", action="store_true", help="do not self-elevate (internal)")
    ap.add_argument("--pause", action="store_true", help="pause at the end (useful when elevated)")
    ap.add_argument("--quiet", action="store_true", help="suppress output (recommended for autostart)")
    ap.add_argument("--install-autostart", action="store_true", help="install autostart (Scheduled Task, startup)")
    ap.add_argument("--uninstall-autostart", action="store_true", help="remove autostart")
    args = ap.parse_args()

    # Если скомпилировано как оконное приложение (без консоли), по умолчанию установлено значение quiet.
    if is_frozen():
        args.quiet = True

    if (not args.no_elevate) and (not is_admin()):
        if not args.quiet:
            print("Administrator privileges are required. Requesting elevation (UAC)...")
        script_abs = self_path()
        forward = sys.argv[1:]
        rc = elevate_self(script_abs, forward)
        if rc != 0 and is_frozen():
            msgbox(
                "Failed to request Administrator privileges (UAC).\n\n"
                "Try:\n"
                "- Right-click TimeCorrect.exe -> Run as administrator\n"
                "- Or install autostart by running:\n"
                "  TimeCorrect.exe --install-autostart\n"
            )
        return rc

    if args.uninstall_autostart:
        return uninstall_autostart(quiet=args.quiet)

    if args.install_autostart:
        return install_autostart(args.ntp, max(0, args.delay_minutes), quiet=args.quiet)

    if is_frozen() and (not task_exists()):
        install_autostart(args.ntp, max(0, args.delay_minutes), quiet=True)

    if not args.quiet:
        print("== TimeCorrect: configure + sync system time ==")
        print(f"NTP: {args.ntp}")

    if not args.quiet:
        print("\n[1/4] Checking Windows Time service (w32time)...")
    run(["sc", "config", "w32time", "start=", "auto"], quiet=args.quiet)
    run(["net", "start", "w32time"], quiet=args.quiet)

    if not args.quiet:
        print("\n[2/4] Configuring NTP source...")
    cfg_rc = run(
        [
            "w32tm",
            "/config",
            f'/manualpeerlist:{args.ntp}',
            "/syncfromflags:manual",
            "/reliable:no",
            "/update",
        ],
        quiet=args.quiet,
    )
    if cfg_rc != 0:
        if not args.quiet:
            print(f"\nERROR: configuration step failed (exit code {cfg_rc}).", file=sys.stderr)
        return 3

    if not args.quiet:
        print("\n[3/4] Forcing time resync...")
    ok = False
    for i in range(1, args.retries + 1):
        if not args.quiet:
            print(f"Attempt {i} of {args.retries}...")
        rc = run(["w32tm", "/resync", "/force"], quiet=args.quiet)
        if rc == 0:
            ok = True
            break
        time.sleep(max(1, args.delay))

    if not args.quiet:
        print("\n[4/4] Time service status:")
    run(["w32tm", "/query", "/status"], quiet=args.quiet)
    run(["w32tm", "/query", "/source"], quiet=args.quiet)

    if ok:
        if not args.quiet:
            print("\nDONE: resync completed.")
        rc = 0
    else:
        if not args.quiet:
            print("\nERROR: resync failed (no fresh time data received).", file=sys.stderr)
            print("Most common cause: UDP port 123 (NTP) blocked by firewall/router/ISP.", file=sys.stderr)
            print("Connectivity test:", file=sys.stderr)
            print(f"  w32tm /stripchart /computer:{args.ntp} /dataonly /samples:5", file=sys.stderr)
        rc = 2

    if args.pause:
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

