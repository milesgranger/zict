from __future__ import annotations

import zipfile
from collections.abc import Iterator
from typing import MutableMapping  # TODO move to collections.abc (needs Python >=3.9)
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # TODO: move to typing on Python 3.8+ and 3.10+ respectively
    from typing_extensions import Literal, TypeAlias

    FileMode: TypeAlias = Literal["r", "w", "x", "a"]


class Zip(MutableMapping[str, bytes]):
    """Mutable Mapping interface to a Zip file

    Keys must be strings, values must be bytes

    Parameters
    ----------
    filename: string
    mode: string, ('r', 'w', 'a'), defaults to 'a'

    Examples
    --------
    >>> z = Zip('myfile.zip')  # doctest: +SKIP
    >>> z['x'] = b'123'  # doctest: +SKIP
    >>> z['x']  # doctest: +SKIP
    b'123'
    >>> z.flush()  # flush and write metadata to disk  # doctest: +SKIP
    """

    filename: str
    mode: FileMode | Literal["closed"]
    _file: zipfile.ZipFile | None

    def __init__(self, filename: str, mode: FileMode = "a"):
        self.filename = filename
        self.mode = mode
        self._file = None

    @property
    def file(self) -> zipfile.ZipFile:
        if self.mode == "closed":
            raise OSError("File closed")
        if not self._file or not self._file.fp:
            self._file = zipfile.ZipFile(self.filename, mode=self.mode)
        return self._file

    def __getitem__(self, key: str) -> bytes:
        return self.file.read(key)

    def __setitem__(self, key: str, value: bytes) -> None:
        self.file.writestr(key, value)

    # FIXME dictionary views https://github.com/dask/zict/issues/61
    def keys(self) -> Iterator[str]:  # type: ignore
        return (zi.filename for zi in self.file.filelist)

    def values(self) -> Iterator[bytes]:  # type: ignore
        return (self.file.read(key) for key in self.keys())

    def items(self) -> Iterator[tuple[str, bytes]]:  # type: ignore
        return ((zi.filename, self.file.read(zi.filename)) for zi in self.file.filelist)

    def __iter__(self) -> Iterator[str]:
        return self.keys()

    def __delitem__(self, key: str) -> None:
        raise NotImplementedError("Not supported by stdlib zipfile")

    def __len__(self) -> int:
        return len(self.file.filelist)

    def flush(self) -> None:
        if self._file:
            if self._file.fp:
                self._file.fp.flush()
            self._file.close()
            self._file = None

    def close(self) -> None:
        self.flush()
        self.mode = "closed"

    def __enter__(self) -> Zip:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
