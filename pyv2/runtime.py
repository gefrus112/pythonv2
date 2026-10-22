"""Capability-based host services for production Python v2 applications.

The language runtime stays deterministic and browser-friendly by default.
Desktop callers explicitly provide :class:`AppRuntime` when a program may use
arguments, app metadata, sandboxed files, bundled assets, or native dialogs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import platform
import tempfile
from typing import Callable, Iterable


MAX_TEXT_BYTES = 8 * 1024 * 1024


class CapabilityError(ValueError):
    """Raised when a program requests a service outside its sandbox."""


@dataclass
class AppRuntime:
    """Explicit host capabilities made available to a Python v2 program.

    ``data_root`` is the only writable tree. ``asset_root`` is an optional,
    read-only tree. Both use resolved paths and reject absolute paths, ``..``,
    and symlink escapes. This gives packaged apps useful persistence without
    granting broad access to the user's machine.
    """

    app_name: str = "Python v2 App"
    app_version: str = "1.0.0"
    app_id: str = "python-v2-app"
    data_root: Path | str | None = None
    asset_root: Path | str | None = None
    argv: Iterable[str] = field(default_factory=tuple)
    platform_name: str = field(default_factory=lambda: platform.system().lower() or os.name)
    message_handler: Callable[[str, str], None] | None = None
    ask_handler: Callable[[str, str, str], str | None] | None = None
    max_text_bytes: int = MAX_TEXT_BYTES

    def __post_init__(self) -> None:
        self.data_root = Path(self.data_root).expanduser().resolve() if self.data_root else None
        self.asset_root = Path(self.asset_root).expanduser().resolve() if self.asset_root else None
        self.argv = tuple(str(value) for value in self.argv)
        if self.max_text_bytes < 1:
            raise ValueError("max_text_bytes must be positive")

    def _resolve(self, root: Path | None, relative: str, service: str) -> Path:
        if root is None:
            raise CapabilityError(f"{service} is not available in this runtime")
        if not isinstance(relative, str) or not relative.strip():
            raise CapabilityError(f"{service} path must be a non-empty string")
        requested = Path(relative)
        if requested.is_absolute():
            raise CapabilityError(f"{service} paths must be relative")
        target = (root / requested).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise CapabilityError(f"{service} path escapes the app sandbox") from exc
        return target

    def data_path(self, relative: str) -> Path:
        return self._resolve(self.data_root, relative, "file access")

    def asset_path(self, relative: str) -> Path:
        return self._resolve(self.asset_root, relative, "asset access")

    def read_text(self, relative: str, *, asset: bool = False) -> str:
        path = self.asset_path(relative) if asset else self.data_path(relative)
        try:
            size = path.stat().st_size
            if size > self.max_text_bytes:
                raise CapabilityError(
                    f"text file is too large ({size} bytes; limit is {self.max_text_bytes})"
                )
            return path.read_text(encoding="utf-8")
        except CapabilityError:
            raise
        except UnicodeDecodeError as exc:
            raise CapabilityError("file is not valid UTF-8 text") from exc
        except OSError as exc:
            raise CapabilityError(str(exc)) from exc

    def write_text(self, relative: str, content: str, *, append: bool = False) -> str:
        encoded = content.encode("utf-8")
        if len(encoded) > self.max_text_bytes:
            raise CapabilityError(
                f"text is too large ({len(encoded)} bytes; limit is {self.max_text_bytes})"
            )
        path = self.data_path(relative)
        try:
            if append and path.exists() and path.stat().st_size + len(encoded) > self.max_text_bytes:
                raise CapabilityError(
                    f"appended file would exceed the {self.max_text_bytes}-byte text limit"
                )
            path.parent.mkdir(parents=True, exist_ok=True)
            if append:
                with path.open("a", encoding="utf-8", newline="") as handle:
                    handle.write(content)
            else:
                # Atomic replacement protects settings and saves from partial writes.
                fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
                try:
                    with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                        handle.write(content)
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(temporary, path)
                except Exception:
                    try:
                        os.unlink(temporary)
                    except OSError:
                        pass
                    raise
        except OSError as exc:
            raise CapabilityError(str(exc)) from exc
        return path.relative_to(self.data_root).as_posix()  # type: ignore[arg-type]

    def exists(self, relative: str, *, asset: bool = False) -> bool:
        path = self.asset_path(relative) if asset else self.data_path(relative)
        return path.is_file()

    def make_dir(self, relative: str) -> str:
        path = self.data_path(relative)
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CapabilityError(str(exc)) from exc
        return path.relative_to(self.data_root).as_posix()  # type: ignore[arg-type]

    def list_dir(self, relative: str = ".") -> list[str]:
        path = self.data_path(relative)
        try:
            if not path.is_dir():
                raise CapabilityError(f"not a directory: {relative}")
            return sorted(item.name for item in path.iterdir())
        except CapabilityError:
            raise
        except OSError as exc:
            raise CapabilityError(str(exc)) from exc

    def delete_file(self, relative: str) -> bool:
        path = self.data_path(relative)
        try:
            if not path.exists():
                return False
            if not path.is_file():
                raise CapabilityError("delete_file() only removes files")
            path.unlink()
            return True
        except CapabilityError:
            raise
        except OSError as exc:
            raise CapabilityError(str(exc)) from exc

    def info(self) -> dict[str, object]:
        return {
            "name": self.app_name,
            "version": self.app_version,
            "id": self.app_id,
            "platform": self.platform_name,
            "data_dir": str(self.data_root) if self.data_root else None,
            "has_assets": self.asset_root is not None,
            "max_text_bytes": self.max_text_bytes,
        }
