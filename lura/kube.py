from lura import logs
from lura.run import run

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
  with run.Log(log, kubectl.log_level):
    return run(argv, cwd=cwd, enforce=enforce)

kubectl.bin = 'kubectl'
kubectl.log_level = log.DEBUG

def get(*args, **opts):
  if 'output' in opts:
    return kubectl('get', args, opts).stdout
  else:
    opts['output'] = 'json'
    return kubectl('get', args, opts).stdout.json()

def describe(*args, **opts):
  return kubectl('describe', args, opts).stdout

def apply(*args, **opts):
  kubectl('apply', args, opts)

def delete(*args, enforce=True, **opts):
  kubectl('delete', args, opts, enforce=enforce)

def logs(*args, **opts):
  return kubectl('logs', args, opts).stdout
