from lura import logs
from lura.run import run
log = logs.get_logger(__name__)

def convert_opts(opts):
  def convert_opt(name, value):
    name = name.replace('_', '-')
    if value in (None, ):
      raise ValueError(
        f'Invalid value for docker-compose argument {name}: {value}')
    elif isinstance(value, bool):
      if value:
        value = None
      else:
        return None
    else:
      value = str(value)
    return f'--{name}' if value is None else f'--{name}={value}'
  argv = []
  for name, value in opts.items():
    converted = convert_opt(name, value)
    if converted is not None:
      argv.extend(converted)
  return argv

def docker_compose(cmd, file=None, args=[], opts={}, cwd=None):
  argv = [docker_compose.bin]
  if file:
    argv.extend(('-f', file))
  argv.append(cmd)
  argv.extend(args)
  argv.extend(convert_opts(opts))
  with run.log(log, docker_compose.log_level):
    return run(argv, cwd=cwd)

docker_compose.bin = 'docker-compose'
docker_compose.log_level = log.DEBUG

def pull(*args, file=None, cwd=None, **opts):
  docker_compose('pull', file, args, opts, cwd)
