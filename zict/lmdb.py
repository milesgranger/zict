from __future__ import annotations

import pathlib
import sys
from collections.abc import Iterable, Iterator

from zict.common import ZictBase


def _encode_key(key: str) -> bytes:
    return key.encode("utf-8")


def _decode_key(key: bytes) -> str:
    return key.decode("utf-8")


class LMDB(ZictBase[str, bytes]):
    """Mutable Mapping interface to a LMDB database.

    Keys must be strings, values must be bytes

    Parameters
    ----------
    directory: str
    map_size: int
        On Linux and MacOS, maximum size of the database file on disk.
        Defaults to 1 TiB on 64 bit systems and 1 GiB on 32 bit ones.

        On Windows, preallocated total size of the database file on disk. Defaults to
        10 MiB to encourage explicitly setting it.

    Examples
    --------
    >>> z = LMDB('/tmp/somedir/')  # doctest: +SKIP
    >>> z['x'] = b'123'  # doctest: +SKIP
    >>> z['x']  # doctest: +SKIP
    b'123'
    """

    def __init__(self, directory: str | pathlib.Path, map_size: int | None = None):
        import lmdb

        if map_size is None:
            if sys.platform != "win32":
                map_size = min(2**40, sys.maxsize // 4)
            else:
                map_size = 10 * 2**20

        self.db = lmdb.open(
            str(directory),
            subdir=True,
            map_size=map_size,
            sync=False,
            writemap=True,
        )

    def __getitem__(self, key: str) -> bytes:
        with self.db.begin() as txn:
            value = txn.get(_encode_key(key))
        if value is None:
            raise KeyError(key)
        return value

    def __setitem__(self, key: str, value: bytes) -> None:
        with self.db.begin(write=True) as txn:
            txn.put(_encode_key(key), value)

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        with self.db.begin() as txn:
            return txn.cursor().set_key(_encode_key(key))

    # FIXME dictionary views https://github.com/dask/zict/issues/61
    def items(self) -> Iterator[tuple[str, bytes]]:  # type: ignore
        cursor = self.db.begin().cursor()
        return ((_decode_key(k), v) for k, v in cursor.iternext(keys=True, values=True))

    def keys(self) -> Iterator[str]:  # type: ignore
        cursor = self.db.begin().cursor()
        return (_decode_key(k) for k in cursor.iternext(keys=True, values=False))

    def values(self) -> Iterator[bytes]:  # type: ignore
        cursor = self.db.begin().cursor()
        return cursor.iternext(keys=False, values=True)

    def _do_update(self, items: Iterable[tuple[str, bytes]]) -> None:
        # Optimized version of update() using a single putmulti() call.
        items_enc = [(_encode_key(k), v) for k, v in items]
        with self.db.begin(write=True) as txn:
            consumed, added = txn.cursor().putmulti(items_enc)
            assert consumed == added == len(items_enc)

    def __iter__(self) -> Iterator[str]:
        return self.keys()

    def __delitem__(self, key: str) -> None:
        with self.db.begin(write=True) as txn:
            if not txn.delete(_encode_key(key)):
                raise KeyError(key)

    def __len__(self) -> int:
        return self.db.stat()["entries"]

    def close(self) -> None:
        self.db.close()
