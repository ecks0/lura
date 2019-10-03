import os
from abc import abstractmethod
from logging import Logger
from lura import fs
from lura import logs
from lura import strutils
from lura import utils
from lura.plates import jinja2
from lura.system import packman
from lura.time import Timer
from multiprocessing import pool
from time import sleep

log = logs.get_logger(__name__)
pause = 0.05

class Cancelled(RuntimeError): pass

class BaseConfiguration(utils.Kwargs):

  log_level = log.INFO

  def __init__(self, **kwargs):
    self._reset()
    super().__init__(**kwargs)

  def _reset(self):
    self.system = None
    self.coordinator = None
    self.packages = None
    self.force = None
    self.purge = None

  def log(self, log, msg, *args, **kwargs):
    if os.linesep in msg:
      msg = strutils.prefix(msg, f'[{self.system.host}] ')
    else:
      msg = f'[{self.system.host}] {msg}'
    if isinstance(log, Logger):
      log[self.log_level](msg)
    elif callable(log):
      log(msg)
    else:
      raise TypeError('"log" must be a Logger or a callable')

  def _wait(self, cond, timeout=None):
    if not self.coordinator:
      return
    if self.coordinator.cancelled:
      raise Cancelled()
    self.coordinator.wait(cond, timeout=timeout)
    if self.coordinator.cancelled:
      raise Cancelled()

  def _ready(self):
    self._wait('ready', timeout=10)

  def sync(self):
    self._wait('sync')

  def _done(self):
    self._wait('done')

  def _cancel(self):
    if self.coordinator and self.coordinator.fail_early:
      self.coordinator.cancelled = True

  def _run(
    self, system, coordinator, on_work, on_start, on_finish, on_error,
    on_cancel, force=None, purge=None
  ):
    self.system = system
    self.coordinator = coordinator
    self.force = force
    self.purge = purge
    try:
      self._ready()
      self.sync()
      self.packages = packman.PackageManagers(system)
      on_start()
      res = on_work()
      on_finish()
      self.sync()
      self._done()
      return res
    except Exception as exc:
      if isinstance(exc, Cancelled):
        on_cancel()
      else:
        self._cancel()
        on_error()
      raise
    finally:
      self._reset()

  @abstractmethod
  def on_apply(self):
    pass

  def on_apply_start(self):
    pass

  def on_apply_finish(self):
    pass

  def on_apply_error(self):
    pass

  def on_apply_cancel(self):
    pass

  def apply(self, system, coordinator=None, force=False):
    self._run(
      system,
      coordinator,
      self.on_apply,
      self.on_apply_start,
      self.on_apply_finish,
      self.on_apply_error,
      self.on_apply_cancel,
      force,
    )

  @abstractmethod
  def on_delete(self):
    pass

  def on_delete_start(self):
    pass

  def on_delete_finish(self):
    pass

  def on_delete_error(self):
    pass

  def on_delete_cancel(self):
    pass

  def delete(self, system, coordinator=None, force=False, purge=False):
    self.log(log, f'Deleting configuration {self.name}')
    self._run(
      system,
      coordinator,
      self.on_delete,
      self.on_delete_start,
      self.on_delete_finish,
      self.on_delete_error,
      self.on_delete_cancel,
      force,
      purge,
    )
    self.log(log, f'Deleted configuration {self.name}')

  def on_is_applied_start(self):
    pass

  def on_is_applied_finish(self):
    pass

  def on_is_applied_error(self):
    pass

  def on_is_applied_cancel(self):
    pass

  @abstractmethod
  def on_is_applied(self):
    pass

  def is_applied(self, system, coordinator=None):
    return self._run(
      system,
      coordinator,
      self.on_is_applied,
      self.on_is_applied_start,
      self.on_is_applied_finish,
      self.on_is_applied_error,
      self.on_is_applied_cancel,
    )

class Configuration(BaseConfiguration):

  name            = '(name not set)'
  assets_object   = None
  os_package_urls = []
  os_packages     = []
  python_packages = []
  directories     = []
  files           = []
  assets          = []
  template_files  = []
  template_assets = []
  symlinks        = []
  template_env    = {}
  keep_os_packages     = True
  keep_python_packages = True

  def __init__(self, **kwargs):
    super().__init__(**kwargs)

  #####
  ## getters

  def get_assets_object(self):
    'Return a `lura.assets.Assets` object.'

    return self.assets_object

  def get_os_package_urls(self):
    "Returns a list of pairs: `('package name', 'package url')`"

    return self.os_package_urls

  def get_os_packages(self):
    'Returns a `list` of os package names.'

    return self.os_packages

  def get_python_packages(self):
    'Returns a `list` of python package names.'

    return self.python_packages

  def get_directories(self):
    'Returns a `list` of directory paths.'

    return self.directories

  def get_files(self):
    'Returns a `list` of pairs: `(src, dst)`'

    return self.files

  def get_assets(self):
    'Returns a `list` of pairs: `(src, dst)`'

    return self.assets

  def get_template_files(self):
    'Returns a `list` of pairs: `(src, dst)`'

    return self.template_files

  def get_template_assets(self):
    'Returns a `list` of pairs: `(src, dst)`'

    return self.template_assets

  def get_symlinks(self):
    'Returns a `list` of pairs: `(src, dst)`'

    return self.symlinks

  def get_template_env(self):
    'Returns the `dict` environment used to evaluate templates.'

    return self.template_env or self.__dict__.copy()

  #####
  ## utilities

  def _tempdir_local(self, *args, prefix=None, **kwargs):
    user_prefix = prefix
    prefix = f'{self.__module__}.{type(self).__name__}.'
    if user_prefix:
      prefix = f'{prefix}.{user_prefix}'
    return fs.TempDir(*args, prefix=prefix, **kwargs)

  def get_all_files(self):
    '''
    Return all files and symlinks (but not directories) applied by this
    configuration.
    '''

    files = []
    files += [file for _, file in self.get_files()]
    files += [file for _, file in self.get_assets()]
    files += [tmpl for _, tmpl in self.get_template_files()]
    files += [tmpl for _, tmpl in self.get_template_assets()]
    files += [symlink for _, symlink in self.get_symlinks()]
    return files

  def refresh_os_package_list(self):
    self.sync()
    if self.get_os_packages() or self.get_os_package_urls():
      self.log(log, 'Refreshing os package list')
      self.packages.os.refresh()

  #####
  ## apply steps

  def apply_os_package_url(self, pkg, url):
    if pkg in self.packages.os:
      self.log(log.debug, f'    {pkg} (present)')
    else:
      self.log(log.debug, f'    {pkg}')
      self.packages.os.install_url(url)

  def apply_os_package_urls(self):
    self.sync()
    os_package_urls = self.get_os_package_urls()
    if not os_package_urls:
      return
    msg = f'Applying {len(os_package_urls)} os package urls'
    if self.packages.os.installed(*[pkg for pkg, _ in os_package_urls]):
      msg += ' (present)'
    self.log(log, msg)
    for pkg, url in os_package_urls:
      self.apply_os_package_url(pkg, url)

  def apply_os_package(self, pkg):
    if pkg in self.packages.os:
      self.log(log.debug, f'    {pkg} (present)')
    else:
      self.log(log.debug, f'    {pkg}')
      self.packages.os.install(pkg)

  def apply_os_packages(self):
    self.sync()
    os_packages = self.get_os_packages()
    if not os_packages:
      return
    msg = f'Applying {len(os_packages)} os packages'
    if self.packages.os.installed(*os_packages):
      msg += ' (present)'
    self.log(log, msg)
    for pkg in os_packages:
      self.apply_os_package(pkg)

  def apply_python_package(self, pkg):
    if pkg in self.packages.pip:
      self.log(log.debug, f'    {pkg} (present)')
    else:
      self.log(log.debug, f'    {pkg}')
      self.packages.pip.install(pkg)

  def apply_python_packages(self):
    self.sync()
    python_packages = self.get_python_packages()
    if not python_packages:
      return
    msg = f'Applying {len(python_packages)} python packages'
    if self.packages.pip.installed(*python_packages):
      msg += ' (present)'
    self.log(log, msg)
    for pkg in python_packages:
      self.apply_python_package(pkg)

  def apply_directory(self, dir):
    if self.system.isdir(dir):
      self.log(log.debug, f'    {dir} (present)')
    else:
      self.log(log.debug, f'    {dir}')
      self.system.mkdirp(dir)

  def apply_directories(self):
    self.sync()
    sys = self.system
    dirs = self.get_directories()
    if not dirs:
      return
    msg = f'Applying {len(dirs)} directories'
    if all(sys.isdir(_ for _ in dirs)):
      self.log(log, f'{msg} (present)')
    else:
      self.log(log, msg)
    for dir in dirs:
      self.apply_directory(dir)

  def apply_file(self, src, dst):
    sys = self.system
    if sys.exists(dst) or sys.islink(dst):
      self.log(log.debug, f'    {dst} (overwrite)')
    else:
      self.log(log.debug, f'    {dst}')
    sys.put(src, dst)

  def apply_files(self):
    self.sync()
    sys = self.system
    files = self.get_files()
    if not files:
      return
    if all(sys.exists(_) for _ in files):
      self.log(log, f'Applying {len(files)} files (present)')
    else:
      self.log(log, f'Applying {len(files)} files')
    for src, dst in files:
      self.apply_file(src, dst)

  def apply_asset(self, src, dst):
    sys = self.system
    assets = self.get_assets_object()
    if sys.exists(dst) or sys.islink(dst):
      self.log(log.debug, f'    {dst} (overwrite)')
    else:
      self.log(log.debug, f'    {dst}')
    with self._tempdir_local('apply_asset') as temp_dir:
      tmp = os.path.join(temp_dir, assets.basename(dst))
      assets.copy(src, tmp)
      self.system.put(tmp, dst)

  def apply_assets(self):
    self.sync()
    assets = self.get_assets()
    if not assets:
      return
    self.log(log, f'Applying {len(assets)} assets')
    for src, dst in assets:
      self.apply_asset(src, dst)

  def apply_template_file(self, env, src, dst):
    sys = self.system
    if sys.exists(dst) or sys.islink(dst):
      self.log(log.debug, f'    {dst} (overwrite)')
    else:
      self.log(log.debug, f'    {dst}')
    with self._tempdir_local('apply_template_file') as temp_dir:
      tmp = os.path.join(temp_dir, os.path.basename(dst))
      jinja2.expandff(env, src, tmp)
      sys.put(tmp, dst)

  def apply_template_files(self):
    self.sync()
    template_files = self.get_template_files()
    if not template_files:
      return
    self.log(log, f'Applying {len(template_files)} template files')
    template_env = self.get_template_env()
    for src, dst in template_files:
      self.apply_template_file(template_env, src, dst)
    self.sync()

  def apply_template_asset(self, env, src, dst):
    sys = self.system
    assets = self.get_assets_object()
    if sys.exists(dst) or sys.islink(dst):
      self.log(log.debug, f'    {dst} (overwrite)')
    else:
      self.log(log.debug, f'    {dst}')
    with self._tempdir_local('apply_template_asset') as temp_dir:
      tmp = os.path.join(temp_dir, os.path.basename(dst))
      tmpl = assets.loads(src)
      jinja2.expandsf(env, tmpl, tmp)
      sys.put(tmp, dst)

  def apply_template_assets(self):
    self.sync()
    template_assets = self.get_template_assets()
    if not template_assets:
      return
    self.log(log, f'Applying {len(template_assets)} template assets')
    template_env = self.get_template_env()
    for src, dst in template_assets:
      self.apply_template_asset(template_env, src, dst)
    self.sync()

  def apply_symlink(self, src, dst):
    sys = self.system
    if sys.islink(dst) or sys.exists(dst):
      self.log(log.debug, log, f'    {dst} (overwrite)')
      sys.rmf(dst)
    else:
      self.log(log.debug, log, f'    {dst}')
    sys.lns(src, dst)

  def apply_symlinks(self):
    self.sync()
    symlinks = self.get_symlinks()
    if not symlinks:
      return
    self.log(log, f'Applying {len(symlinks)} symlinks')
    for src, dst in symlinks:
      self.apply_symlink(src, dst)

  def on_apply_start(self):
    self.sync()
    self.log(log, f'Applying configuration {self.name}')

  def on_apply_finish(self):
    self.sync()
    self.log(log, f'Applied configuration {self.name}')

  def on_apply_error(self):
    msg = f'[{self.system.host}] Unhandled exception while applying'
    log.exception(msg, exc_info=True)

  def on_apply_cancel(self):
    self.log(log, 'Apply cancelled')

  def on_apply(self):
    self.refresh_os_package_list()
    self.apply_os_package_urls()
    self.apply_os_packages()
    self.apply_directories()
    self.apply_files()
    self.apply_assets()
    self.apply_template_files()
    self.apply_template_assets()
    self.apply_symlinks()

  #####
  ## delete steps

  def delete_os_package(self, pkg):
    if pkg not in self.packages.os:
      self.log(log.debug, f'    {pkg} (missing)')
    else:
      self.log(log.debug, f'    {pkg}')
      self.packages.os.remove(pkg)

  def delete_os_packages(self):
    self.sync()
    if self.keep_os_packages:
      self.log(log, 'Keeping os packages')
      return
    self.sync()
    os_packages = reversed(self.get_os_packagess())
    self.log(log, f'Removing {len(os_packages)} os packages')
    for pkg in os_packages:
      self.delete_os_package(pkg)

  def delete_python_package(self, pkg):
    if pkg not in self.packages.pip:
      self.log(log.debug, f'    {pkg} (missing)')
    else:
      self.log(log.debug, f'    {pkg}')
      self.packages.pip.remove(pkg)

  def delete_python_packages(self):
    self.sync()
    if self.keep_python_packages:
      self.log(log, 'Keeping python packages')
      return
    python_packages = reversed(self.get_python_packagess())
    self.log(log, f'Removing {len(python_packages)} python packages')
    for pkg in python_packages:
      self.delete_python_package(pkg)

  def delete_file(self, path):
    sys = self.system
    if sys.exists(path) or sys.islink(path):
      self.log(log.debug, f'    {path}')
      sys.rmf(path)
    else:
      self.log(log.debug, f'    {path} (missing)')

  def delete_files(self):
    self.sync()
    files = list(reversed(self.get_all_files()))
    self.log(log, f'Removing {len(files)} applied files')
    for file in files:
      self.delete_file(file)

  def delete_directory(self, path):
    sys = self.system
    if sys.isdir(path):
      if len(sys.ls(path)) > 0:
        self.log(f'    {path} (not empty, keeping)')
      else:
        self.log(log.debug, f'    {path}')
        os.rmdir(path)
    else:
      self.log(log.debug, f'    {path} (missing)')

  def delete_directories(self):
    self.sync()
    dirs = self.get_directories()
    self.log(log, f'Removing {len(dirs)} applied directories')
    for path in dirs:
      self.delete_directory(path)

  def on_delete_start(self):
    self.sync()
    self.log(log, f'Deleting configuration {self.name}')

  def on_delete_finish(self):
    self.sync()
    self.log(log, f'Deleted configuration {self.name}')

  def on_delete_error(self):
    msg = f'[{self.system.host}] Unhandled exception while deleting'
    log.exception(msg, exc_info=True)

  def on_delete_cancel(self):
    self.log(log, 'Delete cancelled')

  def on_delete(self):
    self.delete_python_packages()
    self.delete_os_packages()
    self.delete_files()
    self.delete_directories()

  #####
  ## predicate

  def on_is_applied(self):
    return (
      all(_ in self.packages.os for _ in self.get_os_packages()) and
      all(_ in self.packages.pip for _ in self.get_python_packages()) and
      all(system.exists(_) or system.islink(_) for _ in self.get_all_files())
    )
