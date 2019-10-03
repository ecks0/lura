import os
from lura import logs
from lura import system
from lura.time import poll
from shlex import quote
from time import sleep

log = logs.get_logger(__name__)

class Minikube(system.Configuration):

  # system.Configuration
  name                   = 'minikube'

  # Minikube
  kube_version           = '1.15.4'
  docker_compose_version = '1.24.1'
  minikube_version       = 'latest'
  helm_version           = '2.14.3'
  vm_driver              = 'none'
  bin_dir                = '/usr/local/bin'

  _docker_compose_url = 'https://github.com/docker/compose/releases/download/%s/docker-compose-Linux-x86_64'
  _kubectl_url = 'https://storage.googleapis.com/kubernetes-release/release/v%s/bin/linux/amd64/kubectl'
  _minikube_url = 'https://storage.googleapis.com/minikube/releases/%s/minikube-linux-amd64'
  _helm_url = 'https://get.helm.sh/helm-v%s-linux-amd64.tar.gz'

  def __init__(self, **kwargs):
    super().__init__(**kwargs)

  def curl_bin(self, url, bin):
    sys = self.system
    path = f'{self.bin_dir}/{bin}'
    if sys.isfile(path):
      self.log(log, f'Applying {path} (present)')
    else:
      self.log(log, f'Applying {path}')
      sys.run(f'curl -L {quote(url)} -o {quote(path)}')
    if not sys.ismode(path, 0o755):
      sys.chmod(path, 0o755)

  def apply_docker_compose_bin(self):
    self.sync()
    url = self._docker_compose_url % self.docker_compose_version
    self.curl_bin(url, 'docker-compose')

  def apply_kubectl_bin(self):
    self.sync()
    url = self._kubectl_url % self.kube_version
    self.curl_bin(url, 'kubectl')

  def apply_kc_bin(self):
    self.sync()
    sys = self.system
    kc_path = '/usr/local/bin/kc'
    if sys.isfile(kc_path):
      self.log(log, f'Applying {kc_path} (present)')
    else:
      self.log(log, f'Applying {kc_path}')
      if not sys.isfile(kc_path):
        sys.dumps(kc_path, self.kc)
    if not sys.ismode(kc_path, 0o755):
      sys.chmod(kc_path, 0o755)

  def apply_minikube_bin(self):
    self.sync()
    url = self._minikube_url % self.minikube_version
    self.curl_bin(url, 'minikube')

  def apply_cluster(self):
    self.sync()
    sys = self.system
    if sys.zero('minikube status'):
      self.log(log, 'Applying cluster (started)')
      return
    self.log(log, 'Applying cluster')
    sys.run("minikube start --kubernetes-version='v%s' --vm-driver=%s" % (
      self.kube_version, self.vm_driver))
    sys.run('kubectl cluster-info')
    sys.run('minikube addons enable ingress')
    sys.run('minikube addons enable storage-provisioner')

  def apply_helm_bin(self):
    self.sync()
    sys = self.system
    bins = ['linux-amd64/helm', 'linux-amd64/tiller']
    apply = False
    for bin in bins:
      path = f'/usr/local/bin/{os.path.basename(bin)}'
      if sys.exists(path):
        self.log(log, f'Applying {path} (present)')
      else:
        self.log(log, f'Applying {path}')
        apply = True
    if not apply:
      return
    url = self._helm_url % self.helm_version
    with sys.tempdir() as temp_dir:
      tar = f'{temp_dir}/helm.tgz'
      sys.run(f'curl -L {quote(url)} -o {tar}')
      sys.run(f"tar xf {tar} -C {self.bin_dir} --strip=1 {' '.join(bins)}")

  def apply_helm(self):
    self.sync()
    sys = self.system
    installed = False
    if sys.zero('kc get pod -n kube-system|grep tiller-deploy'):
      self.log(log, 'Applying helm to cluster (running)')
    else:
      self.log(log, 'Applying helm to cluster')
      self.system.run('helm init --history-max 200')
      installed = True
    argv = "kubectl get pod -n kube-system|grep '^tiller-deploy.* Running '"
    def test():
      return self.system.zero(argv)
    timeout = 45
    if not poll(test, timeout=40, pause=1):
      raise RuntimeError(f'tiller did not start within {timeout} seconds')
    if installed:
      sleep(15)

  def apply_docker_registry(self):
    self.sync()
    sys = self.system
    if sys.zero("kubectl get pod|grep '^docker-registry'"):
      self.log(log, 'Applying docker registry (running)')
      return
    self.log(log, 'Applying docker registry')
    repo = 'stable/docker-registry'
    name = 'docker-registry'
    opts = ','.join([
      'persistence.enabled=true',
      'service.type=NodePort',
      'service.nodePort=32000',
    ])
    sys.run(f'helm install {repo} --name {name} --set {opts}')

  def apply_minikube(self):
    self.apply_docker_compose_bin()
    self.apply_kubectl_bin()
    self.apply_kc_bin()
    self.apply_minikube_bin()
    self.apply_cluster()
    self.apply_helm_bin()
    self.apply_helm()
    self.apply_docker_registry()

  def on_apply_finish(self):
    self.apply_minikube()
    super().on_apply_finish()

  def delete_docker_compose_bin(self):
    pass

  def delete_kubectl_bin(self):
    pass

  def delete_kc_bin(self):
    pass

  def delete_minikube_bin(self):
    pass

  def delete_cluster(self):
    pass

  def delete_helm_bin(self):
    pass

  def delete_docker_registry(self):
    pass

  def delete_minikube(self):
    self.delete_docker_registry()
    self.delete_cluster()
    self.delete_helm_bin()
    self.delete_minikube_bin()
    self.delete_kc_bin()
    self.delete_kubectl_bin()
    self.delete_docker_compose_bin()

  def on_delete_start(self):
    super().on_delete_start()
    self.delete_minikube()

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
