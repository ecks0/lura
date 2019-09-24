from lura import logs
from lura.run import run

log = logs.get_logger(__name__)

def convert_opts(opts):
  def convert_opt(name, value):
    name = name.replace('_', '-')
    if value in (None, ):
      raise ValueError(f'Invalid value for docker argument {name}: {value}')
    elif isinstance(value, bool):
      if value:
        value = None
      else:
        return None
    else:
      value = str(value)
    if value is None:
      return (f'--{name}',)
    else:
      return (f'--{name}', value)
  argv = []
  for name, value in opts.items():
    converted = convert_opt(name, value)
    if converted is not None:
      argv.extend(converted)
  return argv

def docker(cmd, args=[], opts={}, cwd=None, enforce=True):
  argv = [docker.bin, cmd]
  argv.extend(args)
  argv.extend(convert_opts(opts))
  with run.log(log, docker.log_level):
    return run(argv, cwd=cwd, enforce=enforce)

docker.bin = 'docker'
docker.log_level = log.DEBUG

def build(*args, cwd=None, **opts):
  docker('build', args, opts, cwd)

def tag(*args, **opts):
  docker('tag', args, opts)

def push(*args, **opts):
  docker('push', args, opts)

def images(*args, **opts):
  opts['format'] = '{{json .}}'
  return docker('images', args, opts).stdout.json()

def rmi(*args, enforce=True, **opts):
  docker('rmi', args, opts, enforce=enforce)
