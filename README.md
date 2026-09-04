# FastFlowLM RPM packaging

RPM packaging for [FastFlowLM](https://github.com/FastFlowLM/FastFlowLM) on Fedora Linux.

<!--
COPR's own status_image is used here instead of a shields.io dynamic/json badge.
Shields can read the build state out of the COPR API, but its colour is a static
query parameter (color=brightgreen), so a failed build still rendered as a green
badge reading "failed" -- which is how the 2.26.0 breakage sat unnoticed for two
weeks. This image is generated and coloured by COPR itself.
-->

| Package | COPR build |
|---|---|
| [xdna-driver](https://copr.fedorainfracloud.org/coprs/alessandrolattao/fastflowlm/package/xdna-driver/) | [![xdna-driver build status](https://copr.fedorainfracloud.org/coprs/alessandrolattao/fastflowlm/package/xdna-driver/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/alessandrolattao/fastflowlm/package/xdna-driver/) |
| [fastflowlm](https://copr.fedorainfracloud.org/coprs/alessandrolattao/fastflowlm/package/fastflowlm/) | [![fastflowlm build status](https://copr.fedorainfracloud.org/coprs/alessandrolattao/fastflowlm/package/fastflowlm/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/alessandrolattao/fastflowlm/package/fastflowlm/) |

FastFlowLM runs large language models on AMD Ryzen AI XDNA2 NPUs.

## Install

### Fedora

Add the COPR repo:
```sh
sudo dnf copr enable alessandrolattao/fastflowlm
```

Install the driver and runtime (DKMS builds the kernel module automatically):
```sh
sudo dnf install fastflowlm
```

Reboot to activate the NPU driver:
```sh
sudo reboot
```

Download the proprietary NPU kernel binaries (requires internet access to GitHub):
```sh
sudo flm-fetch-kernels
```

Verify the NPU is detected and working:
```sh
flm validate
```

Run a model:
```sh
flm run llama3.2:1b
```

### AlmaLinux / Rocky Linux / RHEL

EPEL is required for `dkms`. Enable it before adding the COPR repo:
```sh
sudo dnf install epel-release
sudo dnf install dkms kernel-devel
```

Add the COPR repo:
```sh
sudo dnf copr enable alessandrolattao/fastflowlm
```

Install the driver and runtime (DKMS builds the kernel module automatically):
```sh
sudo dnf install fastflowlm
```

Reboot to activate the NPU driver:
```sh
sudo reboot
```

Download the proprietary NPU kernel binaries (requires internet access to GitHub):
```sh
sudo flm-fetch-kernels
```

Verify the NPU is detected and working:
```sh
flm validate
```

Run a model:
```sh
flm run llama3.2:1b
```

## Requirements

- AMD Ryzen AI CPU with XDNA2 NPU (Strix, Strix Halo, Kraken, Gorgon Point)
- Linux kernel >= 6.10. On kernel < 7 the `xdna-driver-dkms` module is pulled in automatically (it is the only driver available). On kernel 7+ the kernel's built-in `amdxdna` driver is used by default; the DKMS module is optional there (see [Newer NPUs on kernel 7+](#newer-npus-on-kernel-7))
- NPU firmware >= 1.1.0.0 (installed automatically by `xdna-driver`)
- Unlimited memlock limit: the NPU requires large DMA buffers locked in physical RAM to load model weights. The default kernel limit (64 KB) is far too low. `xdna-driver` sets this automatically via `/etc/security/limits.d/99-amdxdna.conf`. Log out and back in after install for it to take effect

## Newer NPUs on kernel 7+

On kernel 7+ the package uses the kernel's in-tree `amdxdna` driver by default.
That driver tracks the kernel and can lag behind AMD's: on a recent NPU (e.g.
NPU3) or with newer firmware, the in-tree driver may fail to detect the device.

In that case, install the out-of-tree driver module, which ships AMD's newer
`amdxdna` 0.15 and overrides the in-tree one:
```sh
sudo dnf install xdna-driver-dkms
sudo reboot
```

To revert to the in-tree driver, remove it:
```sh
sudo dnf remove xdna-driver-dkms
sudo reboot
```

This only affects the kernel module. It is not needed if `flm validate`
already detects your NPU.

> **Note:** the `xdna-driver` *package* version (e.g. `2.25.0`) is not the same
> as the `amdxdna` *driver* version reported by `flm validate` (e.g. `0.6` or
> `0.15`). On kernel 7+, after a normal `dnf update`, `flm validate` keeps
> showing the in-tree driver version (`0.6`/`0.8`), which is expected. It only
> switches to the newer out-of-tree version after you install `xdna-driver-dkms`
> and reboot.

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
fastflowlm/         fastflowlm.spec + flm-fetch-kernels
xdna-driver/        xdna-driver.spec (XRT + firmware + DKMS kernel module)
.copr/              Makefile used by COPR to generate SRPMs
docs/               Build and publishing guides
Makefile            Targets: srpm, copr, bump, clean
```
