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
    parser.add_argument("--mode", choices=["mock", "camera-only", "gripper-only", "hardware"], default=None)
    args = parser.parse_args()
    config = load_config(args.config)
    mode = args.mode or str(config.get("mode", "mock"))
    if mode == "hardware" and os.environ.get("ARES_R_HARDWARE_CONFIRM") != "YES":
        raise SystemExit("hardware mode requires ARES_R_HARDWARE_CONFIRM=YES")
    controller = build_controller(config, mode)
    try:
        run_terminal(controller)
    finally:
        controller.perception.close()


if __name__ == "__main__":
    main()
