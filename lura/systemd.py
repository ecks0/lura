from lura import logs
from lura.run import run

log = logs.get_logger(__name__)

def convert_opts(opts):
  def convert_opt(name, value):
    name = name.replace('_', '-')
    if value in (None, ):
      raise ValueError(f'Invalid value for argument {name}: {value}')
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

def systemctl(cmd, args, opts, enforce=True, log_level=None):
  log.noise(f'systemctl({cmd}, {args}, {opts})')
  argv = [systemctl.bin, cmd]
  argv.extend(args)
  argv.extend(convert_opts(opts))
  log_level = log_level or systemctl.log_level
  with run.log(log, log_level):
    return run(argv, enforce=enforce)

systemctl.bin = 'systemctl'
systemctl.log_level = log.DEBUG

def journalctl(args, opts, log_level=None):
  log.noise(f'journalctl({args}, {opts})')
  argv = [journalctl.bin]
  argv.extend(args)
  argv.extend(convert_opts(opts))
  log_level = log_level or journalctl.log_level
  with run.log(log, log_level):
    return run(argv)

journalctl.bin = 'journalctl'
journalctl.log_level = log.DEBUG

def start(*args, **opts):
  systemctl('start', args, opts)

def stop(*args, **opts):
  systemctl('stop', args, opts)

def restart(*args, **opts):
  systemctl('restart', args, opts)

def reload(*args, **opts):
  systemctl('reload', args, opts)

def status(*args, **opts):
  return systemctl('status', args, opts, enforce=False).code == 0

def started(svc):
  res = systemctl('status', [svc], {}, enforce=False, log_level=(log.DEBUG))
  return res.code == 0

def enable(*args, **opts):
  systemctl('enable', args, opts)

def disable(*args, **opts):
  systemctl('disable', args, opts)

def daemon_reload(*args, **opts):
  systemctl('daemon-reload', args, opts)

def journal(svc, *args, **opts):
  opts['unit'] = svc
  return str(journalctl(args, opts).stdout)

class Service:

  def __init__(self, name):
    super().__init__()
    self.name = name

  def start(self):
    start(self.name)

  def stop(self):
    stop(self.name)

  def restart(self):
    restart(self.name)

  def reload(self):
    reload(self.name)

  def enable(self):
    enable(self.name)

  def disable(self):
    disable(self.name)

  def is_started(self):
    return started(self.name)

  def is_stopped(self):
    return not started(self.name)

  def journal(self, *args, **opts):
    opts['unit'] = self.name
    return str(journalctl(args, opts).stdout)

  started = property(is_started)
  stopped = property(is_stopped)
