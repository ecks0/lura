import os
from lura import logs
from lura import fs
from lura import run

log = logs.get_logger(__name__)

def convert_opts(opts):
  def convert_opt(name, value):
    name = name.replace('_', '-')
    if value in (None, ):
      raise ValueError(f'Invalid value for git argument {name}: {value}')
    elif isinstance(value, bool):
      if value:
        value = None
      else:
        return None
    return f'--{name}' if value is None else f'--{name}={value}'
  return [
    opt for opt in (convert_opt(name, val) for name, val in opts.items())
    if opt is not None
  ]

def git(cmd, args=[], opts={}, env=None, cwd=None):
  argv = [git.bin, cmd]
  argv.extend(args)
  argv.extend(convert_opts(opts))
  with run.log(log, git.log_level):
    return run(argv, env=env, cwd=cwd)

git.bin = 'git'
git.log_level = log.DEBUG

def clone(*args, env=None, cwd=None, **opts):
  git('clone', args, opts, env, cwd)

def pull(*args, env=None, cwd=None, **opts):
  git('pull', args, opts, env, cwd)

def checkout(*args, env=None, cwd=None, **opts):
  git('checkout', args, opts, env, cwd)

def push(*args, env=None, cwd=None, **opts):
  git('push', args, opts, env, cwd)

class SshKeyEnv(fs.TempDir):

  def __init__(self, key_data=None):
    super().__init__('lura-git', False)
    self.key_data = key_data

  def __enter__(self):
    log.debug('Preparing git ssh authentication')
    temp = super().__enter__()
    key_file = os.path.join(temp, 'id_rsa')
    io.dump(key_file, self.key_data)
    os.chmod(key_file, 0o600)
    ssh_cmd = f"ssh -i '{key_file}' -o StrictHostKeyChecking=no"
    return {'GIT_SSH_COMMAND': ssh_cmd}

class Repo:

  def __init__(self, path, key_data=None):
    super().__init__()
    self.path = path
    self.key_data = key_data

  def clone(self, remote, **opts):
    if self.key_data:
      with SshKeyEnv(self.key_data) as (env):
        clone(remote, self.path, env=env, **opts)
    else:
      clone(remote, (self.path), **opts)

  def pull(self, *args, **opts):
    if self.key_data:
      with SshKeyEnv(self.key_data) as (env):
        pull(args, env=env, cwd=self.path, **opts)
    else:
      pull(args, cwd=self.path, **opts)

  def checkout(self, *args, **opts):
    checkout(args, cwd=self.path, **opts)

  def push(self, *args, **opts):
    if self.key_data:
      with SshKeyEnv(self.key_data) as (env):
        push(args, env=env, cwd=cwd, **opts)
    else:
      push(args, cwd=cwd, **opts)
