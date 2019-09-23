import os
import sys
from abc import abstractmethod
from lura.hash import hashs

class Format:

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

  def print(self, data, *args, **kwargs):
    print(self.dumps(data).rstrip(), *args, **kwargs)
