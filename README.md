# fastflowlm RPM packaging

RPM packaging for [FastFlowLM](https://github.com/FastFlowLM/FastFlowLM) on Fedora Linux.

[![xdna-driver build](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fcopr.fedorainfracloud.org%2Fapi_3%2Fpackage%3Fownername%3Dalessandrolattao%26projectname%3Dfastflowlm%26packagename%3Dxdna-driver%26with_latest_build%3DTrue&query=%24.builds.latest.state&label=xdna-driver&logo=fedora&logoColor=white&labelColor=294172)](https://copr.fedorainfracloud.org/coprs/alessandrolattao/fastflowlm/package/xdna-driver/)
[![fastflowlm build](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fcopr.fedorainfracloud.org%2Fapi_3%2Fpackage%3Fownername%3Dalessandrolattao%26projectname%3Dfastflowlm%26packagename%3Dfastflowlm%26with_latest_build%3DTrue&query=%24.builds.latest.state&label=fastflowlm&logo=fedora&logoColor=white&labelColor=294172)](https://copr.fedorainfracloud.org/coprs/alessandrolattao/fastflowlm/package/fastflowlm/)

FastFlowLM runs large language models on AMD Ryzen AI XDNA2 NPUs.

## Install

**Fedora / AlmaLinux / EPEL:**

```sh
sudo dnf copr enable alessandrolattao/fastflowlm
sudo dnf install fastflowlm
sudo flm-fetch-kernels
flm validate
flm run llama3.2:1b
```

**openSUSE Tumbleweed:**

```sh
sudo zypper addrepo https://copr.fedorainfracloud.org/coprs/alessandrolattao/fastflowlm/repo/opensuse-tumbleweed/alessandrolattao-fastflowlm-opensuse-tumbleweed.repo
sudo zypper install fastflowlm
sudo flm-fetch-kernels
flm validate
flm run llama3.2:1b
```

## Requirements

- AMD Ryzen AI CPU with XDNA2 NPU (Strix, Strix Halo, Kraken, Gorgon Point)
- Linux kernel >= 6.10 (for DKMS kernel module build)
- NPU firmware >= 1.1.0.0 (installed automatically by `xdna-driver`)
- Unlimited memlock limit (set automatically by `xdna-driver` in `/etc/security/limits.d/99-amdxdna.conf`, log out and back in after install)

## About `flm-fetch-kernels`

The NPU kernel binaries (`.so` + xclbin files) are proprietary and cannot be
redistributed in this package. `flm-fetch-kernels` downloads them from the
official FastFlowLM GitHub release and installs them to `/opt/fastflowlm`.

By running `flm-fetch-kernels` you accept the
[FastFlowLM Proprietary Binary License v2.0](https://github.com/FastFlowLM/FastFlowLM/blob/main/LICENSE_BINARY.txt).

## Packages

| Package | Description |
|---|---|
| `fastflowlm` | FastFlowLM CLI and runtime (MIT license) |
| `xdna-driver` | AMD XDNA userspace driver, XRT libraries, NPU firmware, DKMS kernel module (Apache-2.0) |

## Disclaimer

This is an **unofficial, community-maintained** repository. It is not affiliated with, endorsed by, or supported by FastFlowLM Inc. or AMD.

- FastFlowLM software is developed and owned by [FastFlowLM Inc.](https://fastflowlm.com). This repo only provides packaging.
- The NPU kernel binaries downloaded by `flm-fetch-kernels` are subject to the [FastFlowLM Proprietary Binary License v2.0](https://github.com/FastFlowLM/FastFlowLM/blob/main/LICENSE_BINARY.txt). Read it before use.
- Use at your own risk. No warranty, no support, no liability.

## Building locally

See [docs/building-locally.md](docs/building-locally.md).

## Structure

```
fastflowlm/         fastflowlm.spec + flm-fetch-kernels + make_srpm
xdna-driver/        xdna-driver.spec (XRT + firmware + DKMS kernel module) + make_srpm
.copr/              Makefile used by COPR to generate SRPMs
docs/               Build and publishing guides
Makefile            Targets: srpm, copr, bump, clean
```
