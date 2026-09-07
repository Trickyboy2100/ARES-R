"""ARES-R command-line entry point."""

import argparse
import json
import os
from pathlib import Path
from .factory import build_controller
from .terminal import run_terminal


def load_config(path: str):
    with open(path, "r", encoding="utf-8") as stream:
        config = json.load(stream)
    log_dir = Path(config["logging"]["directory"])
    if not log_dir.is_absolute():
        config["logging"]["directory"] = str(Path.cwd() / log_dir)
    return config


def main() -> None:
    parser = argparse.ArgumentParser(description="ARES-R terminal controller")
    parser.add_argument("--config", default="config/system.json")
    parser.add_argument("--enable-hardware", action="store_true",
                        help="connect enabled physical adapters; default is fully offline")
    args = parser.parse_args()
    config = load_config(args.config)
    mode = "hardware-enabled" if args.enable_hardware else "offline"
    if args.enable_hardware and os.environ.get("ARES_R_HARDWARE_CONFIRM") != "YES":
        raise SystemExit("--enable-hardware requires ARES_R_HARDWARE_CONFIRM=YES")
    controller = build_controller(config, mode)
    try:
        run_terminal(controller)
    finally:
        devices = [controller.perception] + list(controller.arms.values()) + list(controller.grippers.values()) + [controller.base]
        for device in devices:
            close = getattr(device, "close", None)
            if close:
                try:
                    close()
                except Exception as exc:
                    print("Cleanup warning: %s" % exc)


if __name__ == "__main__":
    main()
