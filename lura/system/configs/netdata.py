import io
from configparser import ConfigParser
from lura import logs
from lura import system
from lura.attrs import ottr
from lura.hash import hashs
from shlex import quote

log = logs.get_logger(__name__)

class OsBase(system.Configuration):
  'Base class for Debian and RedHat.'

  config_python_packages = [
    'dnspython',
  ]
  config_keep_python_packages = False
  apply_ksm = True

  def setup_python(self):
    # the python package manager will want to use python3, make it use python2
    self.packages.pip._python = 'python2'

  def on_apply_start(self):
    self.setup_python()
    super().on_apply_start()

  def on_delete_start(self):
    self.setup_python()
    super().on_delete_start()

  def on_is_applied_start(self):
    self.setup_python()
    super().on_is_applied_start()

class Debian(OsBase):
  'Install Debian packages needed by netdata and enable rc-local if using ksm.'

  config_name = 'netdata.Debian'
  config_os_packages = [
    'zlib1g-dev',
    'uuid-dev',
    'libuv1-dev',
    'liblz4-dev',
    'libjudy-dev',
    'libssl-dev',
    'libmnl-dev',
    'gcc',
    'make',
    'git',
    'autoconf',
    'autoconf-archive',
    'autogen',
    'automake',
    'pkg-config',
    'curl',
    'python',
    'python-pip',
    'python-ipaddress',
    'lm-sensors',
    'libmnl0',
    'netcat',
  ]

  def apply_rc_local(self):
    sys = self.system
    with self.task('Enable rc.local for ksm') as task:
      if self.apply_ksm == False:
        return
      path = '/etc/rc.local'
      if not sys.exists(path):
        sys.dumps(path, '#!/bin/bash\n')
        +task
      if not sys.ismode(path, 0o755):
        sys.chmod(path, 0o755)
        +task

  def on_apply_finish(self):
    self.apply_rc_local()
    super().on_apply_finish()

class RedHat7(OsBase):
  'Install RedHat7 packages needed by netdata and enable rc-local if using ksm.'

  config_name = 'netdata.RedHat7'
  config_os_package_urls = [
    ('epel-release', 'https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm'),
    ('ius-release',  'https://centos7.iuscommunity.org/ius-release.rpm'),
  ]
  config_os_packages = [
    'automake',
    'curl',
    'gcc',
    'git2u-core',
    'libmnl-devel',
    'libuuid-devel',
    'openssl-devel',
    'libuv-devel',
    'lz4-devel',
    'Judy-devel',
    'make',
    'pkgconfig',
    'python',
    'python-pip',
    'python-ipaddress',
    'zlib-devel',
    'lm_sensors',
    'libmnl',
    'nc',
  ]

  def apply_rc_local(self):
    sys = self.system
    with sys.task('Enable rc.local for ksm') as task:
      if self.apply_ksm == False:
        return
      path = '/etc/rc.d/rc.local'
      if not sys.ismode(path, 0o755):
        sys.chmod(path, 0o755)
        +task

  def on_apply_finish(self):
    self.apply_rc_local()
    super().on_apply_finish()

class Netdata(system.Configuration):

  config_name     = 'netdata.Netdata'
  version         = '1.18.1'
  root_dir        = '/opt'
  apply_ksm       = True
  delete_ksm      = True
  ksm_interval    = 1000

  _ksm = [
    'echo 1 >/sys/kernel/mm/ksm/run',
    'echo 1000 >/sys/kernel/mm/ksm/sleep_millisecs',
  ]

  def __init__(self, **kwargs):
    super().__init__(**kwargs)

  def apply_ksm(self):
    with self.task('Apply kernel samepage merging', log) as task:
      sys = self.system
      if not self.apply_ksm:
        return
      rclocal = sys.loads('/etc/rc.local')
      commands = '\n'.join(self._ksm) + '\n'
      if commands in rclocal:
        return
      rclocal += '\n' + commands
      sys.dumps('/etc/rc.local', rclocal)
      +task
      if sys.loads('/sys/kernel/mm/ksm/run').strip() != '1':
        sys('$SHELL -c "echo 1 >/sys/kernel/mm/ksm/run"')
        +task
      if sys.loads('/sys/kernel/mm/ksm/sleep_millisecs').strip() != '1000':
        sys('$SHELL -c "echo 1000 >/sys/kernel/mm/ksm/sleep_millisecs"')
        +task

  def apply_netdata(self):
    with self.task('Apply netdata', log) as task:
      sys = self.system
      if sys.exists(f'{self.root_dir}/netdata/etc/netdata'):
        return
      with sys.tempdir(prefix='netdata.') as temp_dir:
        repo_dir = f'{temp_dir}/netdata'
        repo_url = 'https://github.com/netdata/netdata'
        args = f'--dont-wait --dont-start-it --install {quote(self.root_dir)}'
        sys(f'git clone {repo_url} {repo_dir}')
        sys(f'git checkout v{self.version}', cwd=repo_dir)
        sys(f'$SHELL netdata-installer.sh {args}', cwd=repo_dir)
      +task

  def on_apply_finish(self):
    self.apply_ksm()
    self.apply_netdata()
    super().on_apply_finish()

  def delete_netdata(self):
    with self.task('Deleting netdata', log) as task:
      sys = self.system
      dir = f'{self.root_dir}/netdata'
      if not sys.exists(dir) or len(sys.ls(dir)) == 0:
        return
      bin_dir = f'{self.root_dir}/netdata/usr/libexec/netdata'
      sys(f'{bin_dir}/netdata-uninstaller.sh -y -f')
      +task

  def delete_leftovers(self):
    with self.task('Deleting leftover files', log) as task:
      sys = self.system
      path = '/etc/systemd/system/multi-user.target.wants/netdata.service'
      if sys.exists(path) or sys.islink(path):
        sys.rmf(path)
        +task

  def delete_ksm(self):
    with self.task('Deleting kernel samepage merging', log) as task:
      sys = self.system
      if not (self.delete_ksm and sys.exists('/etc/rc.local')):
        return
      rclocal = io.StringIO(sys.loads('/etc/rc.local'))
      buf = io.StringIO()
      for line in rclocal:
        if line.strip() in self._ksm:
          continue
        buf.write(line)
      rclocal, buf = rclocal.getvalue(), buf.getvalue()
      if rclocal != buf:
        sys.dumps('/etc/rc.local', buf)
        +task
      if sys.loads('/sys/kernel/mm/ksm/run').strip() == '1':
        sys.dumps('/sys/kernel/mm/ksm/run', '0\n')
        +task

  def on_delete_start(self):
    super().on_delete_start()
    self.delete_netdata()
    self.delete_leftovers()
    self.delete_ksm()

  def on_is_applied(self):
    return (
      super().on_is_applied() and
      self.system.zero('systemctl is-enabled netdata')
    )

class Conf(system.Configuration):

  config_name          = 'netdata.Conf'
  root_dir             = '/opt'
  netdata_conf_changes = None

  def __init__(self, **kwargs):
    super().__init__(**kwargs)

  def get_netdata_conf_changes(self):
    return self.netdata_conf_changes or []

  def apply_netdata_conf_change(self, section, key, value):
    with self.task(f'Apply netdata.conf {section}.{key}', log) as task:
      sys = self.system
      if value is None:
        return
      path = f'{self.root_dir}/netdata/etc/netdata/netdata.conf'
      config = ConfigParser()
      with io.StringIO(sys.loads(path)) as buf:
        config.read_file(buf)
      if (
        section in config and
        key in config[section] and
        config[section][key] == value
      ):
        return
      config.setdefault(section, {})
      config[section][key] = str(value)
      with io.StringIO() as buf:
        config.write(buf)
        sys.dumps(path, buf.getvalue())
      +task

  def apply_netdata_conf_changes(self):
    netdata_conf_changes = self.get_netdata_conf_changes()
    for section, key, value in netdata_conf_changes:
      self.apply_netdata_conf_change(section, key, value)

  def on_apply_finish(self):
    self.apply_netdata_conf_changes()
    super().on_apply_finish()

class Healthd(system.Configuration):

  config_name     = 'netdata.Healthd'
  root_dir        = '/opt'
  healthd_changes = None

  def __init__(self, **kwargs):
    super().__init__(**kwargs)

  def get_healthd_changes(self):
    return self.healthd_changes or []

  def load_checks(self, path):
    sys = self.system
    checks = []
    check = None
    with io.StringIO(sys.loads(path)) as buf:
      for line in buf:
        line = line.strip()
        if not line or line[0] == '#':
          continue
        k, v = line.split(': ', 1)
        if k in ('alarm', 'template'):
          check = ottr()
          checks.append(check)
        check[k] = v
    return checks

  def format_checks(self, checks):
    with io.StringIO() as buf:
      for check in checks:
        field_len = max([len(k) for k in check])
        for (k, v) in check.items():
          if v is None:
            continue
          k = '%s%s' % (' ' * (field_len - len(k)), k)
          buf.write(f'{k}: {v}\n')
        buf.write('\n')
      return buf.getvalue()

  def dump_checks(self, task, path, checks):
    sys = self.system
    contents = self.format_checks(checks)
    created = sys.backuponce(path)
    sys.dumps(path, contents)
    task + (1 + int(created))

  def apply_healthd_change(self, file, selector, update):
    with self.task(f'Apply health.d change {file}', log) as task:
      path = f'{self.root_dir}/netdata/usr/lib/netdata/conf.d/health.d/{file}'
      checks = self.load_checks(path)
      sum_old = hashs(self.format_checks(checks))
      selected = tuple(
        check for check in checks
        if all(k in check and check[k] == v for (k, v) in selector.items())
      )
      if len(selected) == 0:
        return # XXX what to do here
      for check in selected:
        for k in update:
          check[k] = update[k]
      sum_new = hashs(self.format_checks(checks))
      if sum_old != sum_new:
        self.dump_checks(task, path, checks)

  def apply_healthd_changes(self):
    healthd_changes = self.get_healthd_changes()
    for file, selector, update in healthd_changes:
      self.apply_healthd_change(file, selector, update)

  def on_apply_finish(self):
    self.apply_healthd_changes()
    super().on_apply_finish()

class Service(system.Configuration):

  config_name = 'netdata.Service'

  def on_apply_finish(self):
    with self.task('Apply netdata service start', log) as task:
      sys = self.system
      if sys.nonzero('systemctl status netdata'):
        sys('systemctl start netdata')
        +task
    super().on_apply_finish()

  def on_delete_start(self):
    super().on_delete_start()
    with self.task('Apply netdata service stop', log) as task:
      sys = self.system
      if sys.zero('systemctl status netdata'):
        sys('systemctl stop netdata')
        +task

  def on_is_applied(self):
    sys = self.system
    return (
      super().on_is_applied() and
      sys.zero('systemctl status netdata')
    )