import io
import os
from abc import abstractmethod
from lura import fs
from lura import logs
from lura import run
from lura.formats import json
from lura.time import poll

log = logs.get_logger(__name__)

def convert_opts(opts):
  def convert_opt(name, value):
    name = name.replace('_', '-')
    if value in (None, ):
      raise ValueError(f"Invalid value for kubectl argument {name}: {value}")
    elif isinstance(value, bool):
      value = 'true' if value else 'false'
    return f"--{name}={value}"
  return [convert_opt(name, value) for name, value in opts.items()]

def kubectl(cmd, args=[], opts={}, cwd=None, enforce=True):
  log.noise(f"kubectl({cmd}, {args}, {opts}, {cwd}, {enforce}")
  argv = [kubectl.bin, cmd]
  argv.extend(args)
  argv.extend(convert_opts(opts))
  with run.log(log, kubectl.log_level):
    return run(argv, cwd=cwd, enforce=enforce)

kubectl.bin = 'kubectl'
kubectl.log_level = log.DEBUG

def get(*args, **opts):
  if 'output' in opts:
    return kubectl('get', args, opts).stdout
  else:
    opts['output'] = 'json'
    return json.loads(kubectl('get', args, opts).stdout)

def describe(*args, **opts):
  return kubectl('describe', args, opts).stdout

def apply(*args, **opts):
  kubectl('apply', args, opts)

def delete(*args, enforce=True, **opts):
  kubectl('delete', args, opts, enforce=enforce)

def logs(*args, **opts):
  return kubectl('logs', args, opts).stdout

class ResourceFiles(fs.TempDir):

  def __init__(self, resources, keep=False):
    super().__init__(prefix='lura-kube.', keep=keep)
    self.resources = resources

  def __enter__(self):
    log.debug(f'Creating resource files')
    temp_dir = super().__enter__()
    files = []
    for name, resource in self.resources:
      dst = os.path.join(temp_dir, f'{name}.yaml')
      log.debug(f'    {dst}')
      fs.dumps(dst, resource)
      files.append(dst)
    del self.resources
    return files

class Application:

  delete_timeout = 60.0

  def __init__(self, name):
    super().__init__()
    self.name = name

  @abstractmethod
  def _get_resources(self):
    return []

  @abstractmethod
  def _get_pods(self):
    return []

  def get_resources(self):
    return self._get_resources()

  def get_pods(self):
    return self._get_pods()

  def get_manifest(self):
    with io.StringIO() as buf:
      for _, resource in self._get_resources():
        buf.write('---')
        buf.write(os.linesep)
        buf.write(resource.rstrip())
        buf.write(os.linesep)
      return buf.getvalue()

  def is_applied(self):
    return bool(self._get_pods())

  def apply(self):
    log.info(f'Applying {self.name}')
    with ResourceFiles(self._get_resources()) as files:
      for file in files:
        apply(filename=file)

  def delete(self, enforce=True):
    log.info(f'Deleting {self.name}')
    with ResourceFiles(self._get_resources()) as files:
      for file in reversed(files):
        delete(filename=file, enforce=enforce)
    timeout = self.delete_timeout
    if not poll(lambda: not self.is_applied(), timeout=timeout, pause=1):
      raise TimeoutError(f'Application did not stop within {timeout} seconds')

  def logs(self, count):
    pods = self._get_pods()
    if not pods:
      return ''
    with io.StringIO() as buf:
      for pod in pods:
        name = pod.metadata.name
        lines = logs(name, tail=count)
        buf.write(f'----- {name} -----')
        buf.write(os.linesep)
        if lines:
          buf.write(lines.rstrip())
          buf.write(os.linesep)
        buf.write(os.linesep)
      return buf.getvalue()

  manifest = property(get_manifest)
  pods = property(get_pods)
  applied = property(is_applied)
  resources = property(get_resources)
