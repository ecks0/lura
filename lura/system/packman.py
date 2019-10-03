from abc import abstractmethod
from lura import logs

logger = logs.get_logger(__name__)

class PackageManagers:

  def __init__(self, system):
    super().__init__()
    self._system = system
    self._os = None
    self._pip = None

  def get_os(self):
    if self._os is None:
      family = self._system.os.family
      if family == 'Debian':
        self._os = Debian(self._system)
      elif family == 'RedHat':
        self._os = RedHat(self._system)
      else:
        raise ValueError(f'Unsupported os family: {family}')
    return self._os

  def get_pip(self):
    if self._pip is None:
      self._pip = Python(self._system)
    return self._pip

  os = property(get_os)
  pip = property(get_pip)

class PackageManager:

  def __init__(self, system):
    super().__init__()
    self._system = system

  @abstractmethod
  def _get_installed_packages(self):
    "Return a list of `{'package-name': 'package-version'}`."

    pass

  def __contains__(self, package):
    return package in self._get_installed_packages()

  def __getitem__(self, package):
    return self._get_installed_packages().get(package)

  def __iter__(self):
    return self._get_installed_packages().items()

  def installed(self, *packages):
    if len(packages) == 1 and not isinstance(packages[0], str):
      packages = packages[0]
    installed = self._get_installed_packages()
    return all(_ in installed for _ in packages)

  @abstractmethod
  def install(self, *packages):
    pass

  @abstractmethod
  def remove(self, *packages, purge=False):
    pass

  def refresh(self):
    pass

class Debian(PackageManager):

  def __init__(self, system):
    super().__init__(system)

  def _get_installed_packages(self):
    argv = "dpkg-query -W -f='${binary:Package}|${Version}&'"
    packages = self._system.stdout(argv).rstrip('&')
    return dict(pkg.split('|') for pkg in packages.split('&'))

  def install(self, *packages):
    if len(packages) == 1 and not isinstance(packages[0], str):
      packages = packages[0]
    env = {'DEBIAN_FRONTEND': 'noninteractive'}
    self._system.run(f"apt-get install -y {' '.join(packages)}", env=env)

  def install_url(self, *urls):
    raise NotImplementedError()

  def remove(self, *packages, purge=False):
    if len(packages) == 1 and not isinstance(packages[0], str):
      packages = packages[0]
    env = {'DEBIAN_FRONTEND': 'noninteractive'}
    argv = ['apt-get', 'remove', '-y']
    if purge:
      argv.append('--purge')
    argv.extend(packages)
    self._system.run(' '.join(argv), env=env)

  def refresh(self):
    self._system.run('apt-get update')

class RedHat(PackageManager):

  def __init__(self, system):
    super().__init__(system)

  def _get_installed_packages(self):
    argv = "rpm -qa --queryformat '%{NAME}|%{VERSION}&'"
    packages = self._system.stdout(argv).rstrip('&')
    return dict(pkg.split('|') for pkg in packages.split('&'))

  def install(self, *packages):
    if len(packages) == 1 and not isinstance(packages[0], str):
      packages = packages[0]
    packages = [quote(_) for _ in packages]
    self.system.run(f"yum install -y {' '.join(packages)}")

  def install_url(self, *urls):
    if len(urls) == 1 and not isinstance(packages[0], str):
      urls = urls[0]
    return self.install(*urls)

  def remove(self, *packages, purge=False):
    self.system.run(f"yum remove -y {' '.join(packages)}")

class Python(PackageManager):

  pythons = ('python3.7', 'python3.6', 'python3')

  def __init__(self, system):
    super().__init__(system)
    self._python = self._system.which(self.pythons, error=True)

  def _get_installed_packages(self):
    argv = f'{self._python} -m pip list --format json'
    packages = json.loads(self._system.stdout(argv))
    return dict((pkg.name, pkg.get('version')) for pkg in packages)

  def install(self, *packages):
    if len(packages) == 1 and not isinstance(packages[0], str):
      packages = packages[0]
    packages = [quote(_) for _ in packages]
    self._system.run(f"{self._python} -m pip install {' '.join(packages)}")

  def install_url(self, *urls):
    if len(urls) == 1 and not isinstance(urls[0], str):
      urls = urls[0]
    for url in urls:
      self.install(url)

  def remove(self, *packages, purge=False):
    self._system.run(f"yes|{self._python} -m pip remove {' '.join(packages)}")
