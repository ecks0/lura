#!/bin/sh

null() { "$@" >/dev/null 2>&1; return $?; }

null which mypy || null which pytest || {
  echo 'Error: neither mypy nor pytype is installed'
  exit 1
}

clear
#null which mypy && mypy lura | grep -vE 'ruamel|#missing-imports'
null which pytype && pytype lura
