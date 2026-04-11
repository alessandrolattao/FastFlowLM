# Building Locally

Build and test the RPMs on a Fedora machine without uploading to COPR.

## Prerequisites

```sh
sudo dnf install mock rpmlint copr-cli rpmdevtools
sudo usermod -aG mock $USER
newgrp mock
```

## Build xdna-driver first (it's a dependency)

```sh
cd ~/Projects/alessandrolattao/fastflowlm
make srpm-xdna
make mock-xdna
```

RPMs will be in `out/xdna-driver/`.

## Build fastflowlm

For mock to resolve `xdna-driver-devel`, create a local repo from the previously built RPMs:

```sh
mkdir -p /tmp/local-repo
cp out/xdna-driver/*.rpm /tmp/local-repo/
createrepo_c /tmp/local-repo/

# Add the repo to the mock config (one-time setup)
# Edit /etc/mock/fedora-rawhide-x86_64.cfg and add:
#   config_opts['dnf.conf'] += """
#   [local-xdna-driver]
#   name=Local xdna-driver
#   baseurl=file:///tmp/local-repo
#   enabled=1
#   gpgcheck=0
#   """

make srpm-flm
make mock-flm
```

## Lint

```sh
make lint
```

## Quick install test (Fedora container)

```sh
podman run --rm -it \
    -v $(pwd)/out:/rpms:ro \
    fedora:latest \
    bash -c "dnf install -y /rpms/xdna-driver/*.rpm /rpms/fastflowlm/*.rpm && flm --version"
```
