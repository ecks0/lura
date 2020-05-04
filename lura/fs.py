import logging
import os
import sys
import shutil
import tempfile
from lura import utils
from time import sleep
from typing import Any, Callable, Generator, Optional, cast

log = logging.getLogger(__name__)

def load(path: str) -> bytes:
  with open(path, 'rb') as pathf:
    return pathf.read()

def loads(path: str, encoding: Optional[str] = None) -> str:
  encoding = encoding or sys.getdefaultencoding()
  with open(path, 'r', encoding=encoding) as pathf:
    return pathf.read()

def dump(path: str, data: bytes) -> None:
  with open(path, 'wb') as pathf:
    pathf.write(data)

def dumps(path: str, data: str, encoding: Optional[str] = None) -> None:
  encoding = encoding or sys.getdefaultencoding()
  with open(path, 'w', encoding=encoding) as pathf:
    pathf.write(data)

def append(path: str, data: bytes) -> None:
  with open(path, 'ab') as pathf:
    pathf.write(data)

def appends(path: str, data: str, encoding: Optional[str] = None) -> None:
  encoding = encoding or sys.getdefaultencoding()
  with open(path, 'a', encoding=encoding) as pathf:
    pathf.write(data)

def follow(
  path: str,
  interval: float = 0.5,
  cond: Callable = lambda: True
) -> Generator[str, None, None]:
  with open(path) as pathf:
    buf = []
    while cond():
      data = pathf.readline()
      if data == '':
        sleep(interval)
        continue
      if not data.endswith(os.linesep):
        buf.append(data)
        continue
      yield ''.join(buf) + data

class TempDir:

  _tempdir_suffix: Optional[str]
  _tempdir_prefix: Optional[str]
  _tempdir_root: Optional[str]
  _tempdir_keep: bool
  _tempdir_dir: Optional[str]

  def __init__(
    self,
    suffix: Optional[str] = None,
    prefix: Optional[str] = None,
    dir: Optional[str] = None,
    keep: bool = False
  ) -> None:

    super().__init__()
    if prefix is None:
      prefix = 'lura.'
    self._tempdir_suffix = suffix
    self._tempdir_prefix = prefix
    self._tempdir_root = dir
    self._tempdir_keep = keep
    self._tempdir_dir = None

  def __enter__(self) -> str:
    self._tempdir_dir = tempfile.mkdtemp(
      suffix=self._tempdir_suffix, prefix=self._tempdir_prefix,
      dir=self._tempdir_root)
    return self._tempdir_dir

  def __exit__(self, *exc_info: utils.ExcInfo) -> None:
    if self._tempdir_keep:
      log.warn(f'Keeping temporary directory: {self._tempdir_dir}')
    else:
      if self._tempdir_dir:
        shutil.rmtree(self._tempdir_dir)
    self._tempdir_dir = None

class TempFile(TempDir):

  def __enter__(self) -> str:
    temp_dir = super().__enter__()
    return os.path.join(temp_dir, 'file')
