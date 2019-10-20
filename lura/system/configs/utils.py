'Run a shell command.'

from lura import logs
from lura import system
from lura.attrs import ottr
from lura.formats import yaml
from lura.strutils import as_bool
from shlex import quote

log = logs.get_logger(__name__)

class Shell(system.Configuration):

  config_name = 'Shell'
  shell       = '/bin/sh'
  logger      = log
  log_level   = log.INFO

  def get_argv(self):
    return self.args[0]

  def on_apply_finish(self):
    with self.task('Run shell command', log) as task:
      argv = self.get_argv()
      res = self.system.run(f'{self.shell} -i -c {quote(argv)}')
      +task
    quiet = as_bool(self.kwargs.get('quiet', '0'))
    if not quiet:
      fmt = ottr(
        argv = res.args,
        code = res.code,
        stdout = res.stdout,
        stderr = res.stderr,
      )
      self.log(self.logger, yaml.dumps(fmt))
    super().on_apply_finish()

  def on_is_applied(self):
    return False
