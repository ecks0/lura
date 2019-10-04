import os
from lura import logs
from lura import net
from lura import system
from lura.time import poll
from shlex import quote
from time import sleep

log = logs.get_logger(__name__)

class Minikube(system.Configuration):

  # system.Configuration
  name                   = 'minikube'

  # Minikube
  kube_version              = '1.15.4'
  docker_compose_version    = '1.24.1'
  minikube_version          = 'latest'
  helm_version              = '2.14.3'
  vm_driver                 = 'none'
  bin_dir                   = '/usr/local/bin'
  helm_timeout              = 45
  docker_registry_node_port = 32000
  docker_registry_timeout   = 45

  _docker_compose_url = 'https://github.com/docker/compose/releases/download/%s/docker-compose-Linux-x86_64'
  _kubectl_url = 'https://storage.googleapis.com/kubernetes-release/release/v%s/bin/linux/amd64/kubectl'
  _minikube_url = 'https://storage.googleapis.com/minikube/releases/%s/minikube-linux-amd64'
  _helm_url = 'https://get.helm.sh/helm-v%s-linux-amd64.tar.gz'
  _helm_bins = ['linux-amd64/helm', 'linux-amd64/tiller']

  def __init__(self, **kwargs):
    super().__init__(**kwargs)

  #####
  ## apply

  def apply_bin(self, url, bin, sum_url=None, alg='sha256'):
    path = f'{self.bin_dir}/{bin}'
    with self.task(f'Apply {path}', log) as task:
      sys = self.system
      if sys.isfile(path):
        return
      sum = None
      if sum_url:
        sum = sys.wloads(sum_url).rstrip().split()[0]
      sys.wget(url, path, sum, alg)
      sys.chmod(path, 0o755)
      task.change(2)

  def apply_docker_compose_bin(self):
    url = self._docker_compose_url % self.docker_compose_version
    self.apply_bin(url, 'docker-compose', f'{url}.sha256')

  def apply_kubectl_bin(self):
    url = self._kubectl_url % self.kube_version
    self.apply_bin(url, 'kubectl', f'{url}.sha256')

  def apply_kc_bin(self):
    kc_path = f'{self.bin_dir}/kc'
    with self.task(f'Apply {kc_path}', log) as task:
      sys = self.system
      if sys.isfile(kc_path):
        return
      sys.dumps(kc_path, self.kc)
      sys.chmod(kc_path, 0o755)
      task.change(2)

  def apply_minikube_bin(self):
    url = self._minikube_url % self.minikube_version
    self.apply_bin(url, 'minikube', f'{url}.sha256')

  def apply_helm_bin(self, tar, bin):
    path = f'{self.bin_dir}/{os.path.basename(bin)}'
    with self.task(f'Apply {path}', log) as task:
      sys = self.system
      if sys.isfile(path):
        return
      if not sys.exists(tar):
        url = self._helm_url % self.helm_version
        sum = sys.wloads(f'{url}.sha256').rstrip()
        sys.wget(url, tar, sum, 'sha256')
      sys.run(f"tar xf {tar} -C {self.bin_dir} --strip=1 {bin}")
      sys.chmod(path, 0o755)
      task.change(2)

  def apply_helm_bins(self):
    with self.system.tempdir() as temp_dir:
      tar = f'{temp_dir}/helm.tgz'
      for bin in self._helm_bins:
        self.apply_helm_bin(tar, bin)

  def apply_cluster(self):
    with self.task('Apply cluster', log) as task:
      sys = self.system
      if sys.zero('minikube status'):
        return
      sys.run("minikube start --kubernetes-version='v%s' --vm-driver=%s" % (
        self.kube_version, self.vm_driver))
      sys.run('kubectl cluster-info')
      sys.run('minikube addons enable ingress')
      sys.run('minikube addons enable storage-provisioner')
      task.change()

  def apply_helm(self):
    with self.task('Apply helm to cluster', log) as task:
      sys = self.system
      if sys.nonzero('kc get pod -n kube-system|grep tiller-deploy'):
        sys.run('helm init --history-max 200')
        task.change()
    installed = task.changed
    with self.task('Wait for helm', log) as task:
      argv = "kubectl get pod -n kube-system|grep '^tiller-deploy.* Running '"
      test = lambda: sys.zero(argv)
      timeout = self.helm_timeout
      if not poll(test, timeout=timeout, pause=1):
        raise TimeoutError(f'tiller did not start within {timeout} seconds')
      if installed:
        # tiller takes a bit to startup after its deployment begins `Running`
        sleep(15)

  def apply_docker_registry(self):
    with self.task('Apply docker registry', log) as task:
      sys = self.system
      if sys.nonzero("kubectl get pod|grep '^docker-registry'"):
        repo = 'stable/docker-registry'
        name = 'docker-registry'
        opts = ','.join([
          'persistence.enabled=true',
          'service.type=NodePort',
          'service.nodePort=%s' % self.docker_registry_node_port,
        ])
        sys.run(f'helm install {repo} --name {name} --set {opts}')
        task.change()
    with self.task('Wait for docker registry', log) as task:
      argv = "kubectl get pod|grep '^docker-registry.* Running '"
      test = lambda: sys.zero(argv)
      timeout = self.docker_registry_timeout
      if not poll(test, timeout=timeout, pause=1):
        raise TimeoutError(
          f'docker-registry did not start within {timeout} seconds')

  def apply_minikube(self):
    self.apply_docker_compose_bin()
    self.apply_kubectl_bin()
    self.apply_kc_bin()
    self.apply_minikube_bin()
    self.apply_helm_bins()
    self.apply_cluster()
    self.apply_helm()
    self.apply_docker_registry()

  def on_apply_finish(self):
    self.apply_minikube()
    super().on_apply_finish()

  #####
  ## delete

  def delete_bin(self, bin):
    path = f'{self.bin_dir}/{bin}'
    with self.task(f'Delete {bin}', log) as task:
      sys = self.system
      if not sys.isfile(path):
        return
      sys.rmf(path)
      task.change()

  def delete_bins(self):
    bins = list(reversed(list(os.path.basename(_) for _ in self._helm_bins)))
    bins.extend([
      'minikube',
      'kc',
      'kubectl',
      'docker-compose',
    ])
    for bin in bins:
      self.delete_bin(bin)

  def delete_cluster(self):
    with self.task(f'Delete cluster', log) as task:
      sys = self.system
      if sys.nonzero('minikube status'):
        return
      sys.run('minikube delete')
      task.change()

  def delete_docker_registry(self):
    with self.task('Delete docker registry') as task:
      sys = self.system
      deleted = lambda: sys.nonzero("kubectl get pod|grep '^docker-registry'")
      if not deleted():
        self.system.run('helm delete --purge docker-registry')
        task.change()
    with self.task('Wait for docker registry') as task:
      timeout = self.docker_registry_timeout
      if not poll(deleted, timeout=timeout, pause=1):
        raise TimeoutError(
          f'docker-registry did not stop within {timeout} seconds')

  def delete_minikube(self):
    self.delete_docker_registry()
    self.delete_cluster()
    self.delete_bins()

  def on_delete_start(self):
    super().on_delete_start()
    self.delete_minikube()

  def on_is_applied(self):
    sys = self.system
    files = ('minikube', 'kc', 'kubectl', 'docker-compose', 'helm', 'tiller')
    running = lambda n, p: sys.zero(f"kubectl get pod -n {n}|grep '^{p}'")
    return (
      super().on_is_applied() and
      all(sys.isfile(f'{self.bin_dir}/{_}') for _ in files) and
      sys.zero('minikube status') and
      running('default', 'docker-registry') and
      running('kube-system', 'tiller')
    )

Minikube.kc = '''#!/bin/sh
exec kubectl "$@"
'''

class MinikubeDebian(Minikube):

  os_packages = [
    'docker.io',
    'socat',
  ]

  def __init__(self, **kwargs):
    super().__init__(**kwargs)
