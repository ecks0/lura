'System abstractions for ochestration in ssh and local flavors.'

import os
from abc import abstractmethod
from contextlib import contextmanager
from lura import fs
from lura import run
from lura import ssh
from shlex import quote

class System:

  def __init__(self):
    super().__init__()
    self.use_sudo = False

  @abstractmethod
  def put(self, src, dst):
    pass

  @abstractmethod
  def get(self, dst, src):
    pass

  @abstractmethod
  def run(
    self, argv, shell=False, pty=False, env=None, replace_env=False,
    encoding=None, stdin=None, stdout=None, stderr=None, enforce=True
  ):
    pass

  @contextmanager
  def sudo(self):
    orig = self.use_sudo
    self.use_sudo = True
    try:
      yield self
    finally:
      self.use_sudo = orig

  @contextmanager
  def nosudo(self):
    orig = self.use_sudo
    self.use_sudo = False
    try:
      yield self
    finally:
      self.use_sudo = orig

  @contextmanager
  def tempdir(self, prefix=None):
    prefix = prefix or 'lura.system.'
    path = self.run(f'mktemp -d {quote(prefix)}.' + 'X' * 12).stdout.rstrip()
    try:
      yield path
    finally:
      self.rmrf(path)

  def read(self, path):
    with fs.TempDir(prefix='lura-system-read.') as temp_dir:
      dst = f'{temp_dir}/{os.path.basename(path)}'
      self.get(path, dst)
      return fs.loads(dst)

  def write(self, path, data):
    with fs.TempDir(prefix='lura-system-write.') as temp_dir:
      src = f'{temp_dir}/{os.path.basename(path)}'
      fs.dumps(src, data)
      self.put(src, path)

  def whoami(self):
    return self.run('whoami').stdout.rstrip()

  def ls(self, path, long=False):
    argv = f'/bin/ls -a --indicator-style=none {quote(path)}|cat'
    files = self.run(argv).stdout.rstrip().split('\n')
    files = [_ for _ in files if _ not in ('.', '..')]
    if long:
      return [os.path.join(path, _) for _ in files]
    else:
      return files

  def cpf(self, src, dst, preserve=False):
    cp = ['cp', '-f']
    if preserve:
      cp.append('--preserve=all')
    cp.extend((quote(src), quote(dst)))
    cp = ' '.join(cp)
    self.run(cp)

  def cprf(self, src, dst, preserve=False):
    argv = ['cp', '-rf']
    if preserve:
      argv.append('--preserve=all')
    argv.extend((quote(src), quote(dst)))
    argv = ' '.join(argv)
    self.run(argv)

  def mvf(self, src, dst):
    self.run(f'mv -f {quote(src)} {quote(dst)}')

  def rmf(self, path):
    self.run(f'rm -f {quote(path)}')

  def rmrf(self, path):
    self.run(f'rm -rf {quote(path)}')

  def access(self, path, flag):
    raise NotImplementedError(':(')

  def exists(self, path):
    res = self.run(f'test -e {quote(path)}', enforce=False)
    return not bool(res.return_code)

  def isfile(self, path):
    res = self.run(f'test -f {quote(path)}', enforce=False)
    return not bool(res.return_code)

  def isdir(self, path):
    res = self.run(f'test -d {quote(path)}', enforce=False)
    return not bool(res.return_code)

  def islink(self, path):
    res = self.run(f'test -L {quote(path)}', enforce=False)
    return not bool(res.return_code)

  def isfifo(self, path):
    raise NotImplementedError()

  def which(self, *names, error=False):
    names = ' '.join(quote(_) for _ in names)
    return self.run(f'which {names}', enforce=False).stdout.rstrip()

  def chmod(self, path, mode, recurse=False):
    argv = ['chmod']
    if recurse:
      argv.append('-R')
    argv.extend((mode, quote(path)))
    argv = ' '.join(argv)
    self.run(argv)

  def chown(self, path, spec, recurse=False):
    argv = ['chown']
    if recurse:
      argv.append('-R')
    argv.extend((spec, quote(path)))
    argv = ' '.join(argv)
    self.run(argv)

  def chgrp(self, path, group, recurse=False):
    argv = ['chgrp']
    if recurse:
      argv.append('-R')
    argv.extend((group, quote(path)))
    argv = ' '.join(argv)
    self.run(argv)

  def touch(self, path):
    self.run(f'touch {quote(path)}')

  def mkdir(self, dir):
    if self.isdir(dir):
      return
    self.run(f'mkdir {quote(dir)}')

  def mkdirp(self, dir):
    if self.isdir(dir):
      return
    self.run(f'mkdir -p {quote(dir)}')

  def hostname(self):
    return self.run('cat /etc/hostname').stdout.rstrip()

  @property
  def shell(self):
    return self.run('echo $0').stdout.rstrip()

class Local(System):

  def __init__(self, sudo_password=None, sudo_user=None):
    super().__init__()
    self.sudo_password = sudo_password
    self.sudo_user = sudo_user

  def put(self, src, dst):
    self.cpf(src, dst)

  def get(self, dst, src):
    self.cpf(src, dst)

  def run(self, *args, **kwargs):
    if self.use_sudo:
      kwargs['sudo'] = True
      if self.sudo_password:
        kwargs['sudo_password'] = self.sudo_password
      if self.sudo_user:
        kwargs['sudo_user'] = self.sudo_user
    kwargs['shell'] = True
    res = run(*args, **kwargs)
    res.return_code = res.code # like fabric
    return res

  def read(self, path):
    return fs.loads(path)

  def write(self, path, data):
    return fs.writes(path, data)

class Ssh(System):

  def __init__(self, client, sudo_user=None):
    super().__init__()
    self.client = client
    self.sudo_user = sudo_user

  # we want put and get to honor self.use_sudo. fabric's put and get are not
  # sudoable, so far as I can tell. the crude methods below should work in the
  # sudo and non-sudo cases, but this should be improved.

  def put(self, src, dst):
    with self.tempdir() as temp_dir:
      tmpdst = f'{temp_dir}/{os.path.basename(dst)}'
      self.client.put(src, tmpdst)
      self.cpf(tmpdst, dst)

  def get(self, dst, src):
    with self.nosudo():
      whoami = self.whoami()
    with self.tempdir() as temp_dir:
      tmpsrc = f'{temp_dir}/{os.path.basename(src)}'
      self.cpf(src, tmpsrc)
      self.chown(temp_dir, whoami, recurse=True)
      self.client.get(dst, tmpsrc)

  def run(self, *args, **kwargs):
    if self.use_sudo:
      return self.client.sudo(
        *args, user=self.sudo_user, **kwargs)
    else:
      return self.client.run(*args, **kwargs)
