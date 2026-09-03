"""Git-trackable work records for live notes and reconstructed history."""

import argparse
import fcntl
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional


class WorkLog:
    def __init__(self, repository: Path, default_author: str = "unattributed") -> None:
        self.repository = repository.resolve()
        self.daily = self.repository / "worklog" / "daily"
        self.daily.mkdir(parents=True, exist_ok=True)
        self.default_author = default_author

    @staticmethod
    def _line(value: str) -> str:
        return " ".join(value.strip().splitlines())

    def add(self, summary: str, author: Optional[str] = None, source: str = "manual", details: str = "", files: Iterable[str] = (), tests: str = "", next_step: str = "") -> Path:
        now = datetime.now().astimezone()
        path = self.daily / (now.strftime("%Y-%m-%d") + ".md")
        person = author or os.environ.get("ARES_R_AUTHOR") or self.default_author
        entry = [
            "",
            "## %s — %s" % (now.strftime("%H:%M:%S %z"), self._line(summary)),
            "",
            "- Author: %s" % self._line(person),
            "- Source: %s" % self._line(source),
        ]
        file_list = [self._line(item) for item in files if item.strip()]
        if details: entry.append("- Details: %s" % self._line(details))
        if file_list: entry.append("- Files: %s" % ", ".join("`%s`" % item for item in file_list))
        if tests: entry.append("- Verification: %s" % self._line(tests))
        if next_step: entry.append("- Next: %s" % self._line(next_step))
        entry.append("")
        lock_path = self.repository / "logs" / ".worklog.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            new_file = not path.exists()
            with path.open("a", encoding="utf-8") as stream:
                if new_file: stream.write("# Work log — %s\n" % now.strftime("%Y-%m-%d"))
                stream.write("\n".join(entry))
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Append a traceable ARES-R work record")
    sub = parser.add_subparsers(dest="command")
    add = sub.add_parser("add")
    add.add_argument("summary")
    add.add_argument("--author")
    add.add_argument("--source", choices=["manual", "terminal", "reconstructed", "pairing"], default="manual")
    add.add_argument("--details", default="")
    add.add_argument("--files", nargs="*", default=[])
    add.add_argument("--tests", default="")
    add.add_argument("--next", dest="next_step", default="")
    args = parser.parse_args()
    if args.command != "add": parser.error("the add command is required")
    path = WorkLog(Path.cwd()).add(args.summary, args.author, args.source, args.details, args.files, args.tests, args.next_step)
    print(path)


if __name__ == "__main__":
    main()
