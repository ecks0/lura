import sys
import pkg_resources
from typing import Any, IO, Optional, Sequence

class Assets:
  'A thin API around pkg_resources for managing static package assets.'

  package: str
  prefix: Optional[str]

  @classmethod
  def join(cls, *args: str) -> str:
    return '/'.join(arg.rstrip('/') for arg in args)

  @classmethod
  def split(cls, path: str) -> Sequence[str]:
    return path.strip('/').split('/')

  @classmethod
  def basename(cls, path: str) -> str:
    return cls.split(path)[-1]

  @classmethod
  def dirname(cls, path: str) -> str:
    return cls.join(*(cls.split(path)[:-1]))

  def __init__(self, package: str, prefix: Optional[str] = None) -> None:
    super().__init__()
    self.package = package
    self.prefix = prefix

  def path(self, path: str) -> str:
    if self.prefix:
      return self.join(self.prefix, path)
    return path

  def load(self, path: str) -> bytes:
    return pkg_resources.resource_string(self.package, self.path(path))

  def loads(self, path: str, encoding: Optional[str] = None) -> str:
    encoding = encoding or sys.getdefaultencoding()
    buf = pkg_resources.resource_string(self.package, self.path(path))
    return buf.decode(encoding)

  def copy(self, src: str, dst: str) -> None:
    buf = self.load(src)
    with open(dst, 'wb') as file:
      file.write(buf)

  def open(self, path: str) -> IO:
    return pkg_resources.resource_stream(self.package, self.path(path))

  def list(self, path: str, long: bool = False) -> Sequence[str]:
    files = pkg_resources.resource_listdir(self.package, self.path(path))
    if long:
      files = [self.join(path, file) for file in files]
    return files

  def exists(self, path: str) -> bool:
    return pkg_resources.resource_exists(self.package, self.path(path))

  def isdir(self, path: str) -> bool:
    return pkg_resources.resource_isdir(self.package, self.path(path))

  def isfile(self, path: str) -> bool:
    return self.exists(path) and not self.isdir(path)

  def print(self, path: str, *args: Any, **kwargs: Any) -> None:
    print(self.loads(path), *args, **kwargs)

  def bind(self, path: str) -> 'Assets':
    prefix = path
    if self.prefix:
      prefix = self.join(self.prefix, path)
    return type(self)(package=self.package, prefix=prefix)
