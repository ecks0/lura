import os
import stat

def isfifo(path):
  return stat.S_ISFIFO(os.stat(path).st_mode)

def mkfifo(path):
  try:
    os.mkfifo(path)
  except FileExistsError:
    if isfifo(path):
      return
    raise

def dump(data, path, mode='w', encoding=None):
  with open(path, mode=mode, encoding=encoding) as fd:
    fd.write(data)
    fd.flush()

def slurp(path, mode='r', encoding=None):
  with open(path, mode=mode, encoding=encoding) as fd:
    return fd.read()
