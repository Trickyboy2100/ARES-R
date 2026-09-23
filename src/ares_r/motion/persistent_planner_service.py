"""Long-lived cuRobo worker with per-request world updates and one solve."""

import argparse
import contextlib
import json
import os
from pathlib import Path
import socket
import sys
import traceback

from . import production_scene_worker


def serve(path: Path) -> None:
    if path.exists():
        path.unlink()
    server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    server.bind(str(path));os.chmod(path,0o600);server.listen(4)
    try:
        while True:
            connection,_=server.accept()
            with connection:
                request=json.loads(connection.recv(65536).decode())
                if request.get("command")=="stop":
                    connection.sendall(b'{"ok":true}\n');return
                try:
                    log=Path(request["log"]);log.parent.mkdir(parents=True,exist_ok=True)
                    old=sys.argv
                    try:
                        sys.argv=["production_scene_worker",request["request"],request["output"]]
                        with log.open("w") as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
                            production_scene_worker.main()
                    finally:
                        sys.argv=old
                    response={"ok":True,"output":request["output"]}
                except BaseException as exc:
                    response={"ok":False,"error":f"{type(exc).__name__}: {exc}",
                              "traceback":traceback.format_exc()}
                connection.sendall((json.dumps(response)+"\n").encode())
    finally:
        server.close()
        if path.exists(): path.unlink()


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--socket",type=Path,required=True)
    serve(parser.parse_args().socket)
