'Download, extract, configure, and apply kubespray.'

import deepmerge
from getpass import getuser
from lura import system
from lura.formats import yaml
from rba.algo import logs
from shlex import quote
from shutil import which

log = logs.get_logger(__name__)

merge = deepmerge.Merger(
  [
    (dict, ['merge']),
  ],
  ['override'],
  ['override'],
).merge

class Kubespray(system.Configuration):
  '''
  `group_vars` specifies values for kubespray inventory group vars. It is
  a dict with the following structure (for example):
  ```
  {
    'all/all.yml': {
      'upstream_dns_servers': ['8.8.8.8', '8.8.4.4']
    },
    'k8s-cluster/addons.yml': {
      'registry_enabled': True
    },
    'k8s-cluster/k8s-cluster.yml': {
      'kube_version': 'v1.14.7',
      'kube_network_plugin': 'flannel'
    }
  }
  ```
  '''

  # system.Configuration
  name              = 'kubespray'
  python_packages   = ['pipenv']

  # Kubespray
  kubespray_version = '2.11.0'
  inventory_name    = 'lura'
  ssh_username      = getuser()
  ssh_hosts         = []
  login_password    = None
  sudo_password     = None
  group_vars        = None
  connect_timeout   = 180
  pipelining        = True
  set_hostnames     = False
  tty               = False
  keep              = False
  dir               = None
  bin_python        = None
  bin_pipenv        = None

  _tarball_url = 'https://github.com/kubernetes-sigs/kubespray/archive/v%s.tar.gz'

  def __init__(self, **kwargs):
    super().__init__(**kargs)
    self.ssh_hosts = self.check_ssh_hosts(ssh_hosts)
    self.tty = os.isatty(sys.stdout.fileno()) if tty is None else tty

  def check_ssh_hosts(self, ssh_hosts):
    'Ensure that `ssh_hosts` is a list of IP addresses, not hostnames.'

    # FIXME auto-resolve hostnames
    def is_int(c):
      try:
        int(c)
        return True
      except ValueError:
        return False
    def check(host):
      return all(_ == '.' or is_int(_) for _ in host)
    for host in ssh_hosts:
      if not check(host):
        raise ValueError(
          f'ssh_hosts must be ip addresses, hostnames not allowed: {host}')
    return hosts

  def setup_dir(self):
    sys = self.system
    if not self.dir:
      prefix = f'{self.__module__}.{type(self).__name__}'
      self.dir = sys.tempdir(prefix=prefix)
      self.log(log, f'Creating new work dir: {self.dir}')
    else:
      if sys.isdir(self.dir):
        self.log(log, f'Using existing work dir: {self.dir}')
      else:
        self.log(log, f'Creating new work dir: {self.dir}')
        sys.mkdirp(self.dir)

  def configure(self):
    self.log(log, 'Configuring')
    sys = self.system
    self.tarball_url = self._tarball_url % self.kubespray_version
    if not self.bin_python:
      pythons = ('python3.7', 'python3.6', 'python3')
      self.bin_python = sys.which(*pythons, error=True)
    if not self.bin_pipenv:
      self.bin_pipenv = sys.which('pipenv', error=True)
    self.tarball_file = os.path.basename(self.tarball_url)
    self.tarball_path = f'{self.dir}/{self.tarball_file}'
    self.kubespray_dir = f'{self.dir}/kubespray-{self.kubespray_version}'
    self.inventory_dir = f'{self.kubespray_dir}/inventory/{self.inventory_name}'
    self.ssh_hosts_path = f'{self.inventory_dir}/hosts.yml'
    self.vars_dir = f'{self.inventory_dir}/group_vars'
    self.ansible_cfg_path = f'{self.kubespray_dir}/ansible.cfg'

  def download_tarball(self):
    self.log(log, 'Downloading tarball')
    argv = f'curl -L {quote(self.tarball_url)} -o {quote(self.tarball_path)}'
    self.system.run(argv)

  def extract_tarball(self):
    if self.system.isdir(self.kubespray_dir):
      self.log(log, f'Not replacing existing kubespray dir: {self.kubespray_dir}')
    else:
      self.log(log, f'Extracting kubespray: {self.kubespray_dir}')
      self.system.run(f'tar -C {self.dir} -xf {self.tarball_path}')

  def setup_pipenv(self):
    self.log(log, 'Configuring pipenv')
    self.system.run(f'{self.bin_pipenv} install', cwd=self.kubespray_dir)

  def setup_requirements(self):
    self.log(log, 'Installing kubespray requirements')
    req_path = f'{self.kubespray_dir}/requirements.txt'
    sys.run(f'{self.bin_pipenv} install -r {req_path}', cwd=self.kubespray_dir)
    req_path = '%s/contrib/inventory_builder/requirements.txt'
    req_path = req_path % self.kubespray_dir
    sys.run(f'{self.bin_pipenv} install -r {req_path}', cwd=self.kubespray_dir)

  def setup_inventory(self):
    sys = self.system
    if sys.isdir(self.inventory_dir):
      self.log(log, f'Using existing inventory: {self.inventory_dir}')
    else:
      self.log(log, f'Creating new inventory: {self.inventory_dir}')
      sys.cprf(f'{self.kubespray_dir}/inventory/sample', self.inventory_dir)
    self.log(log, 'Configuring inventory')
    env = {'FILE': self.ssh_hosts_path}
    if sys.isfile(self.ssh_hosts_path):
      sys.rmf(self.ssh_hosts_path)
    argv = '%s run %s contrib/inventory_builder/inventory.py %s' % (
      self.bin_pipenv, self.bin_python, ' '.join(self.ssh_hosts))
    sys.run(argv, env=env, cwd=self.kubespray_dir)

  def setup_ansible_cfg(self):
    self.log(log, 'Checking pipelining setting')
    pipelining = str(self.pipelinine)
    cfg = ConfigParser()
    with fs.TempFile() as tmp:
      sys.get(self.ansible_cfg_path, tmp)
      cfg.read(tmp)
      cfg.setdefault('ssh_connection', {})
      if cfg['ssh_connection'].get('pipelining') == pipelining:
        self.log(log, 'Pipelining is enabled')
        return
      self.log(log, 'Enabling pipelining')
      cfg['ssh_connection']['pipelining'] = pipelining
      with open(tmp, 'w') as tmpf:
        cfg.write(tmpf)
      self.system.put(tmp, self.ansible_cfg_path)

  def setup_group_vars(self):
    sys = self.system
    if self.group_vars is None:
      self.log(log, 'No group vars to configure')
      return
    self.log(log, 'Configuring group vars')
    for vars_file in self.group_vars:
      self.log(log, f'    {vars_file}')
      vars_path = f'{self.vars_dir}/{vars_file}'
      with fs.TempFile() as tmp:
        sys.get(vars_path, tmp)
        yaml.dumpf(merge(yaml.loadf(tmp), self.group_vars[vars_file]))
        sys.put(tmp, vars_path)

  def run_ansible(self):
    self.log(log, 'Calling ansible')
    extra_vars = []
    set_hostanems = str(set_hostnames).lower()
    extra_vars.append(f'override_system_hostname={set_hostnames}')
    if self.login_password:
      extra_vars.append(f'ansible_pass={self.login_password}')
    if self.sudo_password:
      extra_vars.append(f'ansible_become_pass={self.sudo_password}')
    argv = '%s run ansible-playbook cluster.yml -i %s -b -u %s' % (
      self.bin_pipenv, self.ssh_hosts_path, self.ssh_username)
    if extra_vars:
      extra_vars = ' '.join(extra_vars)
      argv += f" -e '{extra_vars}'"
    env = dict(
      ANSIBLE_TIMEOUT = str(self.connect_timeout),
      ANSIBLE_INVALID_TASK_ATTRIBUTE_FAILED = 'False',
    )
    self.system.run(argv, env=env, cwd=self.kubespray_dir)

  def cleanup_pipenv(self):
    self.log(log, 'Cleaning up pipenv')
    try:
      run(f'{self.bin_pipenv} --rm', cwd=self.kubespray_dir)
    except Excpetion:
      logger.exception('Unhandled exception while cleaning up pipenv')

  def cleanup_dir(self):
    log = logger[self.log_level]
    if self.keep:
      self.log(log, f'Keeping work dir: {self.dir}')
      return
    if not os.path.isdir(self.work_dir):
      return
    self.system.rmrf(self.dir)

  def apply_kubespray(self):
    log = logger[self.log_level]
    self.log(log, 'Applying kubespray')
    self.setup_dir()
    try:
      self.configure()
      self.download_tarball()
      self.extract_tarball()
      self.setup_pipenv()
      try:
        self.setup_requirements()
        self.setup_inventory()
        self.setup_ansible_cfg()
        self.setup_group_vars()
        self.run_ansible()
      finally:
        self.cleanup_pipenv()
    finally:
      self.cleanup_dir()

  def on_apply_finish(self):
    self.apply_kubespray()
