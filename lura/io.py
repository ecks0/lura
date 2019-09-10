import os
import stat
from distutils.dir_util import copy_tree
from lura import logs
from lura import threads
from pathlib import Path

log = logs.get_logger(__name__)

def flush(file):
  if hasattr(file, 'flush') and callable(file.flush):
    file.flush()

def tee(source, targets, cond=lambda: True):
  while cond():
    data = source.readline()
    if len(data) == '':
      break
    for target in targets:
      target.write(data)

class Tee(threads.Thread):

  def __init__(self, source, targets, name=None):
    super().__init__(target=self.work, name=name)
    self.source = source
    self.targets = targets

  def work(self):
    self.work = True
    tee(self.source, self.targets, lambda: self.work is True)

  def stop(self):
    self.work = False

class LineCallbackWriter:

  def __init__(self):
    super().__init__()
    self.buf = []

  def callback(self, lines):
    for line in lines:
      print(line)

  def write(self, data):
    if os.linesep not in data:
      self.buf.append(data)
      return
    line_end, extra = data.rsplit(os.linesep, 1)
    self.buf.append(line_end)
    lines = ''.join(self.buf).splitlines()
    self.buf.clear()
    if extra:
      self.buf.append(extra)
    self.callback(lines)

  def writelines(self, lines):
    return self.write(''.join(lines))

class LogWriter(LineCallbackWriter):

  def __init__(self, log, level, tag=None):
    super().__init__()
    self.tag = tag
    if isinstance(level, int):
      level = logs.get_level_name(level)
    self.log = getattr(log, level.lower())

  def callback(self, lines):
    for line in lines:
      if self.tag:
        line = f'{self.tag} {line}'
      self.log(line)
