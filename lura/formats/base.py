import os
import sys
from abc import abstractmethod
from lura.hash import hashs
from lura.utils import merge

class Format:
  'Serialize or deserialize data.'

  def __init__(self, *args, **kwargs):
    super().__init__()

  @abstractmethod
  def loads(self, data):
    pass

  @abstractmethod
  def loadf(self, src, encoding=None):
    pass

  @abstractmethod
  def loadfd(self, fd):
    pass

  @abstractmethod
  def dumps(self, data):
    pass

  @abstractmethod
  def dumpf(self, data, dst, encoding=None):
    pass

  @abstractmethod
  def dumpfd(self, data, fd):
    pass

  def mergefs(self, path, patch, encoding=None):
    return merge(self.loadf(path), patch)

  def mergeff(self, path, patch, encoding=None):
    return merge(self.loadf(path), self.loadf(patch))

  def print(self, data, *args, **kwargs):
    print(self.dumps(data).rstrip(), *args, **kwargs)
