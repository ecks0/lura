import os
import sys
import traceback
from abc import abstractmethod
from contextlib import contextmanager
from logging import Logger
from lura import fs
from lura import logs
from lura import strutils
from lura import utils
from lura.attrs import attr
from lura.plates import jinja2
from lura.system import packman
from lura.time import Timer
from multiprocessing import pool
from time import sleep

log = logger = logs.get_logger(__name__)

class Cancel(RuntimeError):

  def __init__(self, config):
    super().__init__('Configuration cancelled')
    self.changes = config.changes

  def update(self, config):
    self.changes += config.changes

class Fail(RuntimeError):

  def __init__(self, config, exc_info):
    super().__init__('Configuration failed')
    self.changes = config.changes
    self.exc_info = exc_info

  def update(self, config):
    self.changes += config.changes

class Task:

  def __init__(
    self, config, msg, log=None, sync=True, silent=False, begin=False
  ):
    super().__init__()
    self.config = config
    self.msg = msg
    self.log = log or logger
    self.sync = sync
    self.silent = silent
    self.begin = begin
    self.changes = 0

  def __enter__(self):
    if self.sync:
      self.config.sync()
    if self.begin and not self.silent:
      self.config.log(self.log, f'( begin) {self.msg}')
    return self

  def __exit__(self, *exc_info):
    assert(self.changes >= 0)
    self.config.changes += self.changes
    if self.silent:
      return
    if exc_info != (None, None, None):
      self.config.log(self.log, f'( error) {self.msg}')
    elif self.changes == 0:
      self.config.log(self.log, f'(    ok) {self.msg}')
    elif self.changes > 0:
      self.config.log(self.log, f'(change) {self.msg}')

  def change(self, count=1):
    assert(count > 0)
    self.changes += count
    return self.changes

  __pos__ = change
  __add__ = change

  def is_changed(self):
    assert(self.changes >= 0)
    return self.changes > 0

  changed = property(is_changed)

  @contextmanager
  def synchronized(self):
    coord = self.config.coordinator
    if coord:
      with coord.rlock:
        yield
    else:
      yield

class BaseConfiguration(utils.Kwargs):

  config_include       = []
  config_task_type     = Task
  config_ready_timeout = 2.0
  config_sync_timeout  = None
  config_done_timeout  = None
  config_packman_type  = packman.PackageManagers

  log_level = log.INFO

  def __init__(self, **kwargs):
    self.reset()
    super().__init__(**kwargs)

  def reset(self):
    self.parent = None
    self.system = None
    self.coordinator = None
    self.packages = None
    self.args = None
    self.kwargs = None
    self.changes = 0

  def task(self, *args, **kwargs):
    return self.config_task_type(self, *args, **kwargs)

  def log(self, log, msg, *args, **kwargs):
    if os.linesep in msg:
      msg = strutils.prefix(msg, f'[{self.system.name}] ')
    else:
      msg = f'[{self.system.name}] {msg}'
    if isinstance(log, Logger):
      log[self.log_level](msg, *args, **kwargs)
    elif callable(log):
      log(msg, *args, **kwargs)
    else:
      raise TypeError('"log" must be a Logger or a callable')

  def _wait(self, cond, timeout=None):
    if not self.coordinator:
      return
    if self.coordinator.cancelled:
      raise Cancel(self)
    self.coordinator.wait(cond, timeout=timeout)
    if self.coordinator.cancelled:
      raise Cancel(self)

  def _ready(self):
    if self.parent:
      self.sync()
    else:
      self._wait('ready', timeout=self.config_ready_timeout)

  def sync(self):
    self._wait('sync', timeout=self.config_sync_timeout)

  def _done(self):
    if self.parent:
      self.sync()
    else:
      self._wait('done', timeout=self.config_done_timeout)

  def _cancel(self):
    if self.coordinator and self.coordinator.fail_early:
      self.coordinator.cancel()

  def _run_includes(self, method):
    include = self.config_include
    if method == 'delete':
      include = reversed(include)
    res = []
    for config in include:
      if isinstance(config, type):
        config = config()
      call = getattr(config, method)
      _ = call(self)
      res.append(_)
    return res

  def _run_method(
    self, method, system, coordinator, on_work, on_start, on_finish, on_error,
    on_cancel, args, kwargs
  ):
    if isinstance(system, BaseConfiguration):
      parent = system
      self.parent = parent
      self.system = parent.system
      self.coordinator = parent.coordinator
      self.args = parent.args
      self.kwargs = parent.kwargs
      self.packages = parent.packages
    else:
      parent = None
      self.system = system
      self.coordinator = coordinator
      self.args = args
      self.kwargs = attr(kwargs)
      self.packages = self.config_packman_type(system)
    try:
      self._ready()
      include_res = self._run_includes(method)
      if method != 'is_applied':
        self.changes += sum(include_res)
      on_start()
      res = on_work()
      if method == 'is_applied':
        res = all(include_res + [res])
        self.applied = res
      on_finish()
      self._done()
      return self.applied if method == 'is_applied' else self.changes
    except Exception as exc:
      if isinstance(exc, Cancel):
        on_cancel()
        exc.update(self)
        raise
      elif isinstance(exc, Fail):
        on_error()
        exc.update(self)
        raise
      else:
        self._cancel()
        on_error()
        raise Fail(self, sys.exc_info())
    finally:
      self.reset()

  @abstractmethod
  def on_apply(self):
    return self.changes

  def on_apply_start(self):
    pass

  def on_apply_finish(self):
    pass

  def on_apply_error(self):
    pass

  def on_apply_cancel(self):
    pass

  def apply(self, system, *args, coordinator=None, **kwargs):
    return self._run_method(
      'apply',
      system,
      coordinator,
      self.on_apply,
      self.on_apply_start,
      self.on_apply_finish,
      self.on_apply_error,
      self.on_apply_cancel,
      args,
      kwargs,
    )

  @abstractmethod
  def on_delete(self):
    return self.changes

  def on_delete_start(self):
    pass

  def on_delete_finish(self):
    pass

  def on_delete_error(self):
    pass

  def on_delete_cancel(self):
    pass

  def delete(self, system, *args, coordinator=None, **kwargs):
    return self._run_method(
      'delete',
      system,
      coordinator,
      self.on_delete,
      self.on_delete_start,
      self.on_delete_finish,
      self.on_delete_error,
      self.on_delete_cancel,
      args,
      kwargs,
    )

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

  def is_applied(self, system, *args, coordinator=None, **kwargs):
    return self._run_method(
      'is_applied',
      system,
      coordinator,
      self.on_is_applied,
      self.on_is_applied_start,
      self.on_is_applied_finish,
      self.on_is_applied_error,
      self.on_is_applied_cancel,
      args,
      kwargs,
    )

class Configuration(BaseConfiguration):

  config_name                 = '(name not set)'
  config_assets_object        = None
  config_os_package_urls      = None
  config_os_packages          = None
  config_python_packages      = None
  config_directories          = None
  config_files                = None
  config_assets               = None
  config_template_files       = None
  config_template_assets      = None
  config_symlinks             = None
  config_template_env         = None
  config_keep_os_packages     = True
  config_keep_python_packages = True
  config_keep_nonempty_dirs   = True

  def __init__(self, **kwargs):
    super().__init__(**kwargs)

  #####
  ## getters

  def get_assets_object(self):
    'Return a `lura.assets.Assets` object.'

    return self.config_assets_object

  def get_os_package_urls(self):
    "Returns a list of pairs: `('package name', 'package url')`"

    return self.config_os_package_urls or []

  def get_os_packages(self):
    'Returns a `list` of os package names.'

    return self.config_os_packages or []

  def get_python_packages(self):
    'Returns a `list` of python package names.'

    return self.config_python_packages or []

  def get_directories(self):
    'Returns a `list` of directory paths.'

    return self.config_directories or []

  def get_files(self):
    'Returns a `list` of pairs: `(src, dst)`'

    return self.config_files or []

  def get_assets(self):
    'Returns a `list` of pairs: `(src, dst)`'

    return self.config_assets or []

  def get_template_files(self):
    'Returns a `list` of pairs: `(src, dst)`'

    return self.config_template_files or []

  def get_template_assets(self):
    'Returns a `list` of pairs: `(src, dst)`'

    return self.config_template_assets or []

  def get_symlinks(self):
    'Returns a `list` of pairs: `(src, dst)`'

    return self.config_symlinks or []

  def get_template_env(self):
    'Returns the `dict` environment used to evaluate templates.'

    return self.config_template_env or self.__dict__.copy()

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

  def get_all_os_packages(self):
    os_packages = [pkg for (pkg, _) in self.get_os_package_urls()]
    os_packages.extend(self.get_os_packages())
    return os_packages

  #####
  ## apply steps

  def apply_os_package_list_update(self):
    msg = 'Apply os package list update'
    os_packages = self.get_all_os_packages()
    silent = not bool(os_packages)
    with self.task(msg, log=log, silent=silent) as task:
      if not os_packages:
        return
      if self.packages.os.installed(os_packages):
        return
      self.packages.os.refresh()
      +task

  def apply_os_package_url(self, task, pkg, url):
    if pkg in self.packages.os:
      return
    self.packages.os.install_url(url)
    +task

  def apply_os_package_urls(self):
    os_package_urls = self.get_os_package_urls()
    msg = f'Apply {len(os_package_urls)} os package urls'
    silent = not bool(os_package_urls)
    with self.task(msg, log=log, silent=silent) as task:
      for pkg, url in os_package_urls:
        self.apply_os_packages(task, pkg, url)

  def apply_os_package(self, task, pkg):
    if pkg in self.packages.os:
      return
    self.packages.os.install(pkg)
    +task

  def apply_os_packages(self):
    os_packages = self.get_os_packages()
    msg = f'Apply {len(os_packages)} os package(s)'
    silent = not bool(os_packages)
    with self.task(msg, log=log, silent=silent) as task:
      for pkg in os_packages:
        self.apply_os_package(task, pkg)

  def apply_python_package(self, task, pkg):
    if pkg in self.packages.pip:
      return
    self.packages.pip.install(pkg)
    +task

  def apply_python_packages(self):
    python_packages = self.get_python_packages()
    msg = f'Apply {len(python_packages)} python package(s)'
    silent = not bool(python_packages)
    with self.task(msg, log=log, silent=silent) as task:
      for pkg in python_packages:
        self.apply_python_package(task, pkg)

  def apply_directory(self, task, dir):
    sys = self.system
    if sys.isdir(dir):
      return
    sys.mkdirp(dir)
    +task

  def apply_directories(self):
    directories = self.get_directories()
    msg = f'Apply {len(directories)} directories'
    silent = not bool(directories)
    with self.task(msg, log=log, silent=silent) as task:
      for dir in directories:
        self.apply_directory(task, dir)

  def apply_file(self, task, src, dst):
    sys = self.system
    if sys.isfile(dst):
      return
    sys.put(src, dst)
    +task

  def apply_files(self):
    files = self.get_files()
    msg = f'Apply {len(files)} files'
    silent = not bool(files)
    with self.task(msg, log=log, silent=silent) as task:
      for src, dst in files:
        self.appy_file(task, src, dst)

  def apply_asset(self, task, src, dst):
    sys = self.system
    if sys.isfile(dst):
      return
    assets = self.get_assets_object()
    with self._tempdir_local(prefix='apply_asset') as temp_dir:
      tmp = os.path.join(temp_dir, assets.basename(dst))
      assets.copy(src, tmp)
      sys.put(tmp, dst)
    +task

  def apply_assets(self):
    assets = self.get_assets()
    msg = f'Apply {len(assets)} assets'
    silent = not bool(assets)
    with self.task(msg, log=log, silent=silent) as task:
      for src, dst in assets:
        self.apply_asset(task, src, dst)

  def apply_template_file(self, task, src, dst):
    sys = self.system
    if sys.isfile(dst):
      return
    env = self.get_template_env()
    with self._tempdir_local(prefix='apply_template_file') as temp_dir:
      tmp = os.path.join(temp_dir, os.path.basename(dst))
      jinja2.expandff(env, src, tmp)
      sys.put(tmp, dst)
    +task

  def apply_template_files(self):
    template_files = self.get_template_files()
    msg = f'Apply {len(template_files)} template files'
    silent = not bool(template_files)
    with self.task(msg, log=log, silent=silent) as task:
      for src, dst in template_files:
        self.apply_template_file(task, src, dst)

  def apply_template_asset(self, task, src, dst):
    sys = self.system
    if sys.isfile(dst):
      return
    assets = self.get_assets_object()
    env = self.get_template_env()
    with self._tempdir_local(prefix='apply_template_asset') as temp_dir:
      tmp = os.path.join(temp_dir, os.path.basename(dst))
      tmpl = assets.loads(src)
      jinja2.expandsf(env, tmpl, tmp)
      sys.put(tmp, dst)
    +task

  def apply_template_assets(self):
    template_assets = self.get_template_assets()
    msg = f'Apply {len(template_assets)} template assets'
    silent = not bool(template_assets)
    with self.task(msg, log=log, silent=silent) as task:
      for src, dst in template_assets:
        self.apply_template_asset(task, src, dst)

  def apply_symlink(self, task, src, dst):
    sys = self.system
    if sys.islink(dst):
      return
    sys.lns(src, dst)
    +task

  def apply_symlinks(self):
    symlinks = self.get_symlinks()
    msg = f'Apply {len(symlinks)} symlinks'
    silent = not bool(symlinks)
    with self.task(msg, log=log, silent=silent) as task:
      for src, dst in symlinks:
        self.apply_symlink(task, src, dst)

  def on_apply(self):
    self.apply_os_package_list_update()
    self.apply_os_package_urls()
    self.apply_os_packages()
    self.apply_python_packages()
    self.apply_directories()
    self.apply_files()
    self.apply_assets()
    self.apply_template_files()
    self.apply_template_assets()
    self.apply_symlinks()
    return super().on_apply()

  def on_apply_start(self):
    super().on_apply_start()

  def on_apply_finish(self):
    super().on_apply_finish()

  def on_apply_error(self):
    super().on_apply_error()

  def on_apply_cancel(self):
    super().on_apply_cancel()

  #####
  ## delete steps

  def delete_os_package(self, task, pkg):
    if pkg not in self.packages.os:
      return
    self.packages.os.remove(pkg)
    +task

  def delete_os_packages(self):
    os_packages = list(reversed(self.get_all_os_packages()))
    msg = f'Delete {len(os_packages)} os package(s)'
    silent = not bool(os_packages)
    with self.task(msg, log=log, silent=silent) as task:
      if self.config_keep_os_packages:
        return
      for pkg in os_packages:
        self.delete_os_package(task, pkg)

  def delete_python_package(self, task, pkg):
    if pkg not in self.packages.pip:
      return
    self.packages.pip.remove(pkg)
    +task

  def delete_python_packages(self):
    python_packages = self.get_python_packages()
    msg = f'Delete {len(python_packages)} python package(s)'
    silent = not bool(python_packages)
    with self.task(msg, log=log, silent=silent) as task:
      if self.config_keep_python_packages:
        return
      for pkg in python_packages:
        self.delete_python_package(task, pkg)

  def delete_file(self, task, path):
    sys = self.system
    if not (sys.isfile(path) or sys.islink(path)):
      return
    sys.rmf(path)
    +task

  def delete_files(self):
    files = self.get_all_files()
    msg = f'Delete {len(files)} files'
    silent = not bool(files)
    with self.task(msg, log=log, silent=silent) as task:
      for file in files:
        self.delete_file(task, file)

  def delete_directory(self, task, dir):
    sys = self.system
    if not sys.isdir(dir):
      return
    if self.config_keep_nonempty_dirs and len(sys.ls(dir)) > 0:
      return
    sys.rmrf(dir)
    +task

  def delete_directories(self):
    directories = self.get_directories()
    msg = f'Delete {len(directories)} directories'
    silent = not bool(directories)
    with self.task(msg, log=log, silent=silent) as task:
      for dir in directories:
        self.delete_directory(task, dir)

  def on_delete(self):
    self.delete_python_packages()
    self.delete_os_packages()
    self.delete_files()
    self.delete_directories()
    return super().on_delete()

  def on_delete_start(self):
    super().on_delete_start()

  def on_delete_finish(self):
    super().on_delete_finish()

  def on_delete_error(self):
    super().on_delete_error()

  def on_delete_cancel(self):
    super().on_delete_cancel()

  #####
  ## predicate steps

  def on_is_applied(self):
    sys = self.system
    return (
      all(_ in self.packages.os for (_, __) in self.get_os_package_urls()) and
      all(_ in self.packages.os for _ in self.get_os_packages()) and
      all(_ in self.packages.pip for _ in self.get_python_packages()) and
      all(sys.exists(_) or sys.islink(_) for _ in self.get_all_files())
    )

  def on_is_applied_start(self):
    super().on_is_applied_start()

  def on_is_applied_finish(self):
    super().on_is_applied_finish()

  def on_is_applied_error(self):
    super().on_is_applied_error()

  def on_is_applied_cancel(self):
    super().on_is_applied_cancel()
