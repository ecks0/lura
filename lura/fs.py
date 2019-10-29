import logging
import os
import sys
import shutil
import tempfile
from time import sleep

log = logging.getLogger(__name__)

def load(path):
  with open(path, 'rb') as pathf:
    return pathf.read()

def loads(path, encoding=None):
  encoding = encoding or sys.getdefaultencoding()
  with open(path, 'r', encoding=encoding) as pathf:
    return pathf.read()

def dump(path, data):
  with open(path, 'wb') as pathf:
    pathf.write(data)

def dumps(path, data, encoding=None):
  encoding = encoding or sys.getdefaultencoding()
  with open(path, 'w', encoding=encoding) as pathf:
    pathf.write(data)

def append(path, data):
  with open(path, 'ab') as pathf:
    pathf.write(data)

def appends(path, data, encoding=None):
  encoding = encoding or sys.getdefaultencoding()
  with open(path, 'a', encoding=encoding) as pathf:
    patf.write(data)

def follow(path, interval=0.5, cond=lambda: True):
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

  def __init__(self, suffix=None, prefix=None, dir=None, keep=False):
    super().__init__()
    if prefix is None:
      prefix = 'lura.'
    self._tempdir_suffix = suffix
    self._tempdir_prefix = prefix
    self._tempdir_root = dir
    self._tempdir_keep = keep
    self._tempdir_dir = None

  def __enter__(self):
    self._tempdir_dir = tempfile.mkdtemp(
      suffix=self._tempdir_suffix, prefix=self._tempdir_prefix,
      dir=self._tempdir_root)
    return self._tempdir_dir

  def __exit__(self, *exc_info):
    if self._tempdir_keep:
      log.warn(f'Keeping temporary directory: {self._tempdir_dir}')
    else:
      shutil.rmtree(self._tempdir_dir)
    self._tempdir_dir = None

class TempFile(TempDir):

  def __init__(self, *args, **kwargs):
    super().__init__()

  def __enter__(self):
    temp_dir = super().__enter__()
    return os.path.join(temp_dir, 'file')
