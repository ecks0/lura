import os
from lura import fs
from lura import logs
from lura.plates import jinja2

log = logs.get_logger(__name__)

class Installer:

  def __init__(self, name, assets=None):
    super().__init__()
    self.name = name
    self.assets = assets

  def get_directories(self):
    return []

  def get_files(self):
    return []

  def get_assets(self):
    return []

  def get_template_files(self):
    return []

  def get_template_assets(self):
    return []

  def get_symlinks(self):
    return []

  def get_template_env(self):
    return {}

  def get_install_files(self):
    files = []
    files += [file for _, file in self.get_files()]
    files += [file for _, file in self.get_assets()]
    files += [tmpl for _, tmpl in self.get_template_files()]
    files += [tmpl for _, tmpl in self.get_template_assets()]
    files += [symlink for _, symlink in self.get_symlinks()]
    return files

  def create_directory(self, dir):
    if os.path.isdir(dir):
      log.info(f'    {dir} (exists)')
    else:
      log.info(f'    {dir}')
      os.makedirs(dir)

  def create_directories(self):
    dirs = self.get_directories()
    log.info(f'Creating {len(dirs)} directories')
    for dir in dirs:
      self.create_directory(dir)

  def copy_file(self, src, dst):
    if os.path.exists(dst) or os.path.islink(dst):
      log.info(f'    {dst} (overwrite)')
    else:
      log.info(f'    {dst}')
    fs.copy(src, dst)

  def copy_files(self):
    files = self.get_files()
    log.info(f'Copying {len(files)} files')
    for src, dst in files:
      self.copy_file(src, dst)

  def copy_asset(self, src, dst):
    if os.path.exists(dst) or os.path.islink(dst):
      log.info(f'    {dst} (overwrite)')
    else:
      log.info(f'    {dst}')
    self.assets.copy(src, dst)

  def copy_assets(self):
    assets = self.get_assets()
    log.info(f'Copying {len(assets)} assets')
    for src, dst in assets:
      self.copy_asset(src, dst)

  def expand_template_file(self, env, src, dst):
    if os.path.exists(dst) or os.path.islink(dst):
      log.info(f'    {dst} (overwrite)')
    else:
      log.info(f'    {dst}')
    jinja2.expandff(env, src, dst)

  def expand_template_files(self):
    template_files = self.get_template_files()
    log.info(f'Expanding {len(template_files)} template files')
    template_env = self.get_template_env()
    for src, dst in template_files:
      self.expand_template_file(template_env, src, dst)

  def expand_template_asset(self, env, src, dst):
    if os.path.exists(dst) or os.path.islink(dst):
      log.info(f'    {dst} (overwrite)')
    else:
      log.info(f'    {dst}')
    tmpl = self.assets.loads(src)
    jinja2.expandsf(env, tmpl, dst)

  def expand_template_assets(self):
    template_assets = self.get_template_assets()
    log.info(f'Expanding {len(template_assets)} template assets')
    template_env = self.get_template_env()
    for src, dst in template_assets:
      self.expand_template_asset(template_env, src, dst)

  def create_symlink(self, src, dst):
    if os.path.islink(dst) or os.path.exists(dst):
      log.info(f'    {dst} (overwrite)')
      os.unlink(dst)
    else:
      log.info(f'    {dst}')
    os.symlink(src, dst)

  def create_symlinks(self):
    symlinks = self.get_symlinks()
    log.info(f'Creating {len(symlinks)} symlinks')
    for src, dst in symlinks:
      self.create_symlink(src, dst)

  def remove_file(self, path):
    if os.path.exists(path) or os.path.islink(path):
      log.info(f'    {path}')
      os.unlink(path)
    else:
      log.info(f'    {path} (missing)')

  def remove_files(self):
    files = list(reversed(self.install_files))
    log.info(f'Removing {len(files)} installed files')
    for file in files:
      self.remove_file(file)

  def remove_directory(self, path):
    if os.path.isdir(path):
      if len(os.listdir(path)) > 0:
        log.warn(f'    {path} (not empty, keeping)')
      else:
        log.info(f'    {path}')
        os.rmdir(path)
    else:
      log.info(f'    {path} (missing)')

  def remove_directories(self):
    dirs = self.get_directories()
    log.info(f'Removing {len(dirs)} installed directories')
    for path in dirs:
      self.remove_directory(path)

  def on_install_start(self, force):
    pass

  def on_install_finish(self, force):
    pass

  def install(self, force=False):
    log.info(f'Install starting for {self.name}')
    self.on_install_start(force)
    self.create_directories()
    self.copy_files()
    self.copy_assets()
    self.expand_template_files()
    self.expand_template_assets()
    self.create_symlinks()
    self.on_install_finish(force)
    log.info(f'Install finished for {self.name}')

  def on_uninstall_start(self, force):
    pass

  def on_uninstall_finish(self, force):
    pass

  def uninstall(self, force=False):
    log.info(f'Uninstall starting for {self.name}')
    self.on_uninstall_start(force)
    self.remove_files()
    self.remove_directories()
    self.on_uninstall_finish(force)
    log.info(f'Uninstall finished for {self.name}')

  def is_installed(self):
    installed = any(os.path.exists(path) for path in self.install_files)
    if installed:
      log.debug(f'{self.name} is installed')
    else:
      log.debug(f'{self.name} is not installed')
    return installed

  install_files = property(get_install_files)
  installed = property(is_installed)
