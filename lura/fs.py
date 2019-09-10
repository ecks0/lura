import os
import stat
import tempfile
from lura import logs

log = logs.get_logger(__name__)

def dump(path, data, mode='w', encoding=None):
  with open(path, mode=mode, encoding=encoding) as (fd):
    fd.write(data)

def slurp(path, mode='r', encoding=None):
  with open(path, mode=mode, encoding=encoding) as (fd):
    return fd.read()

def tempdir(prefix=''):
  if prefix:
    if prefix[(-1)] != '-':
      prefix = f'{prefix}-'
  tmpdir = tempfile.mkdtemp(prefix=prefix)
  log.debug(f'Created temp dir: {tmpdir}')
  return tmpdir

class ScratchDir:
  '''
  Like `tempfile.TemporaryDirectory`, but optionally can be kept, and has a
  more manageable name.
  '''

  def __init__(self, prefix='', keep=False):
    super().__init__()
    self._prefix = prefix
    self._keep = keep

  def __enter__(self):
    self._dir = tempdir(self._prefix)
    log.debug(f'Created scratch directory: {self._dir}')
    return self._dir

  def __exit__(self, *exc_info):
    if self._keep:
      log.info(f'Keeping scratch directory: {self._dir}')
    else:
      rmr(self._dir)
    del self._dir

def copy(src, dst):
  from lura.run import run
  with run.Log(log, log.DEBUG):
    run(['cp', '-rf', src, dst])

def rm(path):
  from lura.run import run
  log.debug(f'Removing files: {path}')
  if isinstance(path, str):
    path = [path]
  argv = ['rm', '-f'] + list(path)
  with run.Log(log, log.DEBUG):
    run(argv)

def rmr(path):
  from lura.run import run
  log.debug(f'Removing files recursively: {path}')
  if isinstance(path, str):
    path = [path]
  argv = ['rm', '-rf'] + list(path)
  with run.Log(log, log.DEBUG):
    run(argv)

def make_parent_dirs(path):
  dir = os.path.dirname(path)
  if not os.path.isdir(dir):
    os.makedirs(dir)

def isfifo(path):
  return stat.S_ISFIFO(os.stat(path).st_mode)

def touch(path, mode=0o600):
  Path(path).touch(mode=mode)

def fext(path):
  return path.rsplit('.', 1)[1] if '.' in path else None
