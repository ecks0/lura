import pickle
from lura.formats import base

class Format(base.Format):

  def __init__(self):
    super().__init__()

  def loads(self, data):
    return pickle.loads(data)

  def loadf(self, src, encoding=None):
    with open(src, mode='rb', encoding=encoding) as fd:
      return self.loadfd(fd)

  def loadfd(self, fd):
    return pickle.load(fd)

  def dumps(self, data):
    return pickle.dumps(data)

  def dumpf(self, data, dst, encoding=None):
    with open(dst, mode='wb', encoding=encoding) as fd:
      self.dumpfd(data, fd)

  def dumpfd(self, data, fd):
    pickle.dump(data, fd)
    if hasattr(fd, 'flush') and callable(fd.flush):
      fd.flush()
