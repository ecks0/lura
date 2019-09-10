import sys
import pkg_resources

class Assets:

  @staticmethod
  def join(*args):
    return '/'.join(arg.rstrip('/') for arg in args)

  def __init__(self, package, prefix=None):
    super().__init__()
    self.package = package
    self.prefix = prefix

  def path(self, path):
    if self.prefix:
      return self.join(self.prefix, path)
    return path

  def load(self, path):
    return pkg_resources.resource_string(self.package, self.path(path))

  def loads(self, path, encoding=None):
    encoding = encoding or sys.getdefaultencoding()
    buf = pkg_resources.resource_string(self.package, self.path(path))
    return buf.decode(encoding)

  def copy(self, src, dst):
    buf = self.load(src)
    with open(dst, 'wb') as file:
      file.write(buf)

  def open(self, path):
    return pkg_resources.resource_stream(self.package, self.path(path))

  def list(self, path, long=False):
    files = pkg_resources.resource_listdir(self.package, self.path(path))
    if long:
      files = [self.join(path, file) for file in files]
    return files

  def exists(self, path):
    return pkg_resources.resource_exists(self.package, self.path(path))

  def isdir(self, path):
    return pkg_resources.resource_isdir(self.package, self.path(path))

  def isfile(self, path):
    return self.exists(path) and not self.isdir(path)

  def print(self, path, *args, **kwargs):
    print(self.loads(path), *args, **kwargs)
