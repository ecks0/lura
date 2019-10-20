'Local and ssh systems implemented using gnu coreutils.'

import os
from abc import abstractmethod
from contextlib import contextmanager
from lura import fs
from lura import logs
from lura import run
from lura import ssh
from lura.attrs import attr
from shlex import quote

log = logs.get_logger(__name__)

class System:

  def __init__(self, name=None):
    super().__init__()
    self._name = name

  @property
  @abstractmethod
  def host(self):
    pass

  @property
  def name(self):
    return self._name or self.host

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

  @property
  def __call__(self):
    return self.run

class Coreutils(System):

  def __init__(self, name=None, sudo=False):
    super().__init__(name)
    self.sudo_use = sudo
    self.sudo_user = None
    self.sudo_login = True

  @contextmanager
  def sudo(self, user=None, login=True):
    o_sudo_use = self.sudo_use
    o_sudo_user = self.sudo_user
    o_sudo_login = self.sudo_login
    self.sudo_use = True
    self.sudo_user = user
    self.sudo_login = login
    try:
      yield self
    finally:
      self.sudo_use = o_sudo_use
      self.sudo_user = o_sudo_user
      self.sudo_login = o_sudo_login

  @contextmanager
  def nosudo(self):
    o_sudo_use = self.sudo_use
    self.sudo_use = False
    try:
      yield self
    finally:
      self.sudo_use = o_sudo_use

  def zero(self, *args, **kwargs):
    kwargs.setdefault('enforce', False)
    return self.run(*args, **kwargs).return_code == 0

  def nonzero(self, *args, **kwargs):
    kwargs.setdefault('enforce', False)
    return self.run(*args, **kwargs).return_code != 0

  def stdout(self, *args, **kwargs):
    return self.run(*args, **kwargs).stdout

  def lines(self, *args, **kwargs):
    return self.run(*args, **kwargs).stdout.rstrip('\n').split('\n')

  @contextmanager
  def tempdir(self, prefix=None):
    user_prefix = prefix
    prefix = 'lura.system.coreutils.'
    if user_prefix:
      prefix = f'{prefix}{user_prefix}'
    argv = f'mktemp -p /tmp -d {quote(prefix)}' + 'X' * 12 # FIXME
    path = self.run(argv).stdout.rstrip()
    try:
      yield path
    finally:
      self.rmrf(path)

  def _tempdir_local(self, *args, prefix=None, **kwargs):
    user_prefix = prefix
    prefix = f'{self.__module__}.{type(self).__name__}.'
    if user_prefix:
      prefix = f'{prefix}{user_prefix}'
    return fs.TempDir(*args, prefix=prefix, **kwargs)

  def load(self, path):
    with self._tempdir_local(prefix='load.') as temp_dir:
      dst = f'{temp_dir}/{os.path.basename(path)}'
      self.get(path, dst)
      return fs.load(dst)

  def loads(self, path, encoding=None):
    with self._tempdir_local(prefix='loads.') as temp_dir:
      dst = f'{temp_dir}/{os.path.basename(path)}'
      self.get(path, dst)
      return fs.loads(dst, encoding=encoding)

  def dump(self, path, data):
    with self._tempdir_local(prefix='dump.') as temp_dir:
      src = f'{temp_dir}/{os.path.basename(path)}'
      fs.dump(src, data)
      self.put(src, path)

  def dumps(self, path, data, encoding=None):
    with self._tempdir_local(prefix='dumps.') as temp_dir:
      src = f'{temp_dir}/{os.path.basename(path)}'
      fs.dumps(src, data, encoding=encoding)
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

  def ln(self, src, dst):
    self.run(f'ln {quote(src)} {quote(dst)}')

  def lns(self, src, dst):
    self.run(f'ln -s {quote(src)} {quote(dst)}')

  def hash(self, path, alg='sha512'):
    return self.run(f'{alg}sum {quote(path)}').stdout.split()[0]

  def exists(self, path):
    return self.zero(f'test -e {quote(path)}', enforce=False)

  def isfile(self, path):
    return self.zero(f'test -f {quote(path)}', enforce=False)

  def isdir(self, path):
    return self.zero(f'test -d {quote(path)}', enforce=False)

  def islink(self, path):
    return self.zero(f'test -L {quote(path)}', enforce=False)

  def isfifo(self, path):
    return self.run(f'stat -c %F {quote(path)}').stdout.rstrip() == 'fifo'

  def ismode(self, path, mode):
    if isinstance(mode, int):
      mode = oct(mode)[2:]
    file_mode = self.run(f'stat -c %a {quote(path)}').stdout.rstrip()
    return mode == file_mode

  def ishash(self, path, sum, alg='sha512'):
    return sum == self.hash(path, alg)

  def iscontents(self, path, data):
    return self.hash(path, alg='sha512') == hash.hashs(data, alg='sha512')

  def isfilecontents(self, path, local_file):
    return self.hash(path, alg='sha512') == hash.hashf(local_file, alg='sha512')

  def readlink(self, path):
    return self.run(f'readlink {quote(path)}').stdout.rstrip()

  def which(self, *names, error=False):
    for name in names:
      path = self.run(f'which {quote(name)}', enforce=False).stdout.rstrip()
      if path:
        return path
    else:
      if error:
        raise FileNotFoundError(f'Binary is missing: {",".join(names)}')

  def chmod(self, path, mode, recurse=False):
    if isinstance(mode, int):
      mode = oct(mode)[2:]
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

  def rmdir(self, dir):
    if not self.isdir(dir):
      return
    self.run(f'rmdir {qoute(dir)}')

  def backuponce(self, path, end='.dist'):
    backup = f'{path}{end}'
    if self.exists(backup):
      return False
    self.cpf(path, backup)
    return True

  def wget(self, url, path, sum=None, alg='sha512'):
    url, path = quote(url), quote(path)
    if self.which('curl'):
      self.run(f'curl -L {url} -o {path}')
    elif self.which('wget'):
      self.run(f'wget {url} -O {path}')
    else:
      raise FileNotFoundError('neither curl nor wget were found on the system')
    if not sum:
      return
    path_sum = self.hash(path, alg)
    if path_sum != sum:
      self.rmf(path)
      msg = '%s sum mismatch for %s\nExpected: %s\nReceived: %s'
      raise ValueError(msg % (alg, path, sum, path_sum))

  def wload(self, url, sum=None, alg='sha512'):
    with self.tempdir(prefix='wload.') as temp_dir:
      tmp = f'{temp_dir}/file'
      wget(url, path, sum, alg)
      return self.load(tmp)

  def wloads(self, url, sum=None, alg='sha512', encoding=None):
    with self.tempdir(prefix='wloads.') as temp_dir:
      tmp = f'{temp_dir}/file'
      self.wget(url, tmp, sum, alg)
      return self.loads(tmp, encoding=encoding)

  @property
  def hostname(self):
    if self.which('hostname'):
      return self.run('hostname').stdout.rstrip()
    hostname = self.run('echo $HOSTNAME').stdout.rstrip()
    if len(hostname) > 0:
      return hostname
    if self.isfile('/etc/hostname'):
      return self.run('cat /etc/hostname').stdout.rstrip()
    raise RuntimeError('Unable to determine system hostname')

  @property
  def shell(self):
    return self.run('echo $0').stdout.rstrip()

  @property
  def python(self, error=False):
    return self.which('python3.7', 'python3.6', 'python3', error=error)

  @property
  def os(self):
    # FIXME lol
    if self.which('apt-get', 'apt'):
      return attr(family='debian')
    elif self.which('yum'):
      return attr(family='redhat')
    else:
      raise RuntimeError('Unable to determine operating system')

  def apply(self, config, *args, **kwargs):
    config = config() if isinstance(config, type) else config
    return config.apply(self, *args, **kwargs)

  def delete(self, config, *args, **kwargs):
    config = config() if isinstance(config, type) else config
    return config.delete(self, *args, **kwargs)

  def is_applied(self, config, *args, **kwargs):
    config = config() if isinstance(config, type) else config
    return config.is_applied(self, *args, **kwargs)

class Local(Coreutils):

  def __init__(self, name=None, sudo=False, sudo_password=None):
    super().__init__(name=name, sudo=sudo)
    self.sudo_password = sudo_password

  @property
  def host(self):
    return 'localhost'

  def put(self, src, dst):
    self.cpf(src, dst)

  def get(self, src, dst):
    with self.nosudo():
      user = self.whoami()
      group = self.run('id -gn').stdout.strip()
    self.cpf(src, dst)
    self.chown(dst, user)
    self.chgrp(dst, group)

  def run(self, argv, *args, **kwargs):
    if self.sudo_use:
      kwargs['sudo'] = True
      if self.sudo_user:
        kwargs['sudo_user'] = self.sudo_user
      if self.sudo_password:
        kwargs['sudo_password'] = self.sudo_password
      if self.sudo_login is True:
        kwargs['sudo_login'] = True
    argv = ['sh', '-c', argv] # FIXME
    res = run(argv, *args, **kwargs)
    res.return_code = res.code
    res.command = res.args
    return res

class Ssh(Coreutils):

  def __init__(self, *args, name=None, sudo=False, **kwargs):
    super().__init__(name=name, sudo=sudo)
    self._client = ssh.Client(*args, **kwargs)

  @property
  def host(self):
    return self._client._host

  def put(self, src, dst):
    with self.nosudo():
      whoami = self.whoami()
    with self.tempdir(prefix='put.') as temp_dir:
      tmp = f'{temp_dir}/{os.path.basename(dst)}'
      self.chown(temp_dir, whoami)
      self._client.put(src, temp_dir)
      self.cpf(tmp, dst)

  def get(self, src, dst):
    with self.nosudo():
      whoami = self.whoami()
    with self.tempdir(prefix='get.') as temp_dir:
      tmpsrc = f'{temp_dir}/{os.path.basename(src)}'
      self.cpf(src, tmpsrc)
      self.chown(temp_dir, whoami, recurse=True)
      self._client.get(tmpsrc, dst)

  def run(self, argv, *args, **kwargs):
    if self.sudo_use:
      res = self._client.sudo(
        argv, *args, user=self.sudo_user, login=self.sudo_login, **kwargs)
      res.code = res.return_code
      res.args = res.command
      return res
    else:
      return self._client.run(argv, *args, **kwargs)
