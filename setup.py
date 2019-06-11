from setuptools import setup, find_packages

install_requires = [
  'cryptography >= 2.7',
  'Jinja2 >= 2.10',
  'PyYAML >= 3.13',
]

setup(
  name = 'lura',
  version = "0.0.1",
  author = 'Nicholas A. Zigarovich',
  author_email = 'nick@zigarovich.io',
  description = 'syntactic sugar',
  packages = find_packages(),
  python_requires = ">= 3.6",
  install_requires = install_requires,
  include_package_data = True,
)
