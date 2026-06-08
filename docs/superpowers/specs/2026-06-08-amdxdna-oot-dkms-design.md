# Design: bump xdna-driver to the AMD 1.8 release (amdxdna 0.15) with an optional OOT DKMS module

- Date: 2026-06-08
- Status: approved (brainstorming), pending implementation plan
- Scope: the `xdna-driver` package (base + `-dkms` subpackage), its build system
  (`Makefile`, `.copr/Makefile`), and the `check-updates` workflow. No change to
  `fastflowlm`.

## Background

`flm validate` reports the loaded NPU driver as `amdxdna version: X.Y`. That is
the DRM `major.minor` of the kernel module, not the version of our `xdna-driver`
RPM (which tracks the XRT version).

On Fedora 44 (kernel 7.0.x) the loaded module is the **in-tree** driver shipped
by the kernel: `/lib/modules/<k>/kernel/drivers/accel/amdxdna/`. Its version
follows the kernel:

- in-tree, our kernel 7.0.10 -> **0.6** ("Support preemption")
- in-tree, mainline `master` -> **0.8** ("Support BO usage query")
- AMD out-of-tree repo (`drivers/accel/amdxdna`) -> **0.15**

The `0.6 -> 0.15` delta (version-history comment in
`drivers/accel/amdxdna/amdxdna_pci_drv.c`) is all telemetry/diagnostics plus
**new device-type support** (notably **NPU3 at 0.12**). There is **no
inference-performance feature** in this range; inference speed comes from
firmware + the proprietary NPU kernels + `flm`, not the DRM driver.

### Why this matters

The in-tree driver does not know newer NPU device types (NPU3) and can reject
newer firmware. See amd/xdna-driver #1074 and #1219. On newer machines the
in-tree 0.6/0.8 driver can fail to drive the NPU at all. Our box (npu4, FW
1.1.2.64) works today; this is about **enabling newer hardware (npu3)**.

## Findings that shaped this design (all verified)

1. **0.15 lives only on a branch, not a tag.** The AMD repo has exactly **one
   git tag** (`2.21.75`) and **no releases**. It ships via **numbered release
   branches** (`1.4` ... `1.8`). `drivers/accel` (0.15) exists only on **`1.8`**
   (HEAD `039c0d3528a340266203c5b48f41ed61262af67b`, 2026-06-08) and `main`.
   Branches `1.7` and older have only the legacy `src/driver/amdxdna` tree.
2. **The module 0.15 builds clean OOT on our kernel.** `amdxdna.ko` from
   `drivers/accel/amdxdna` compiled against Fedora kernel 7.0.10-201 with
   `-Werror`, no patches, no extra deps. Portability over 6.10 -> 7.x is handled
   by `drivers/accel/tools/configure_kernel.sh` (autoconf-style feature
   detection -> `config_kernel.h`), already aware of 7.0/7.2.
3. **Firmware npu3 ships only on 1.8.** `tools/info.json`: tag 2.21.75 has
   npu1/npu2/npu4/npu5; branch 1.8 has npu1/**npu3**/npu4/npu5. The new hardware
   needs both the 0.15 driver (knows NPU3) AND the npu3 firmware (only on 1.8) —
   so taking only the module would be useless. The **full bump is required.**
4. **No Epoch needed.** The package version tracks the **XRT version**, not the
   branch name. XRT on tag 2.21.75 is **2.21**; XRT on branch 1.8 is **2.25**
   (`src/CMake/settings.cmake`: `XRT_VERSION_MAJOR 2` / `MINOR 25`). So the
   package goes `2.21.75 -> 2.25.x`, a **natural upgrade** — `dnf update` pulls
   it for everyone, no Epoch, no COPR build deletion, no manual reinstall.
5. **AMD's DKMS config for this tree is a CMake template.**
   `drivers/accel/CMake/config/dkms.conf.in` has `@`-placeholders
   (`@XDNA_DKMS_PKG_NAME@`, `@MAKE_DRV@`, `@MODULE_DRV@`, ...) and **no
   `BUILD_EXCLUSIVE_KERNEL_MAX`** — i.e. AMD intends it to build on any kernel
   >= 6.10, including 7+.

## Goal

Bump `xdna-driver` to the AMD **1.8** release so the package ships the 0.15
driver source, the npu3 firmware, and XRT 2.25; and have the `-dkms` subpackage
build the **0.15 `amdxdna.ko`** as an **optional** upgrade over the in-tree
driver for users whose NPU the in-tree driver cannot drive — without changing
behaviour for everyone whose in-tree driver already works.

## Non-goals

- No inference-performance claims (the 0.15 delta has none).
- Do not force the OOT module on systems where the in-tree driver works.
- No change to `fastflowlm`.
- No Epoch (not needed — version increases naturally).

## Design decisions

### 1. Source ref: pin the `1.8` branch by commit

The build system currently clones the tag named by `Version` (`BRANCH=$VER`).
Since 0.15 has no tag, clone the **`1.8` branch pinned to a commit SHA** for
reproducibility. Record the pinned SHA in the spec (e.g.
`%global amd_commit 039c0d3528a340266203c5b48f41ed61262af67b`) so the source of
truth is the spec, not a moving branch.

### 2. Package version: XRT scheme, no Epoch

`Version` tracks XRT major.minor (`2.25`) with a patch we pick (start `2.25.0`;
the upstream `XRT_VERSION_PATCH` is a build number injected via env, not in the
source, so we own the patch field). `2.25.0 > 2.21.75`, so `dnf update` upgrades
everyone with no Epoch. Bump `Release` to `1%{?dist}` on the version change.

### 3. `-dkms` builds 0.15 from `drivers/accel`

- DKMS source: `drivers/accel/amdxdna` + `drivers/accel/tools/` (for
  `configure_kernel.sh`) + the `include/` headers it needs (the validated build
  staged `drivers/accel/amdxdna`, `drivers/accel/tools`, `include/`).
- `dkms.conf`: reconstruct from AMD's `dkms.conf.in` for this tree.
  `PACKAGE_NAME=xrt-amdxdna` (keep the current DKMS name so `--rpm_safe_upgrade`
  continuity holds), `BUILD_EXCLUSIVE_KERNEL_MIN=6.10`, **no MAX** (build on 7+
  too), `PRE_BUILD="./configure_kernel.sh"`, `BUILT_MODULE_NAME[0]=amdxdna`. The
  exact `MAKE`/`BUILT_MODULE_LOCATION`/`DEST_MODULE_LOCATION` values are
  determined by a spike task that validates with `dkms build` (see plan), based
  on the working manual build:
  `make -C <kernel-build> M=<srcdir> OFT_CONFIG_AMDXDNA_PCI=y
  OFT_CONFIG_AMDXDNA_OF=n modules` after running `configure_kernel.sh`.
- This also corrects a current bug: the existing `-dkms` builds the **legacy**
  `src/driver/amdxdna` tree (`amdxdna_legacy.ko`), not the primary module.

### 4. Install behaviour: conditional auto-pull, opt-in otherwise

Keep the existing conditional `Recommends` (discriminator = does the kernel
already have amdxdna in-tree; on Fedora that boundary is 7.0):

| Kernel | In-tree amdxdna? | OOT `-dkms` | NPU runs on |
|--------|------------------|-------------|-------------|
| < 7.0 | no | **auto-pulled** (Recommends) | OOT 0.15 |
| >= 7.0 | yes (0.6/0.8) | **opt-in** (manual install) | in-tree by default; OOT 0.15 if installed |

Rationale for not forcing it on 7+: those machines gain no useful feature from
0.15 (no perf, no hardware they lack) but would take on real risk — a module
that compiles but regresses at runtime, a DKMS build that breaks after a future
kernel bump (silently dropping NPU for anyone depending on it), or a
firmware/driver mismatch. "Worst case it just doesn't compile" is the *lucky*
case (falls back to in-tree); the others are worse.

### 5. In-tree override + reversibility

- OOT module installs into a modules dir that wins over in-tree `kernel/` in
  `depmod` order (`extra/` or `updates/`); confirm precedence with the chosen
  `DEST_MODULE_LOCATION`.
- **No permanent blacklist** of the in-tree module: on package removal DKMS
  removes the OOT module, `depmod` re-runs, and the in-tree driver loads again
  next boot. Removal is a clean revert.

### 6. Build system: clone branch+commit instead of tag

`Makefile` (`build-srpm`) and `.copr/Makefile` derive `BRANCH=$VER` and clone
that tag. Change both to clone the `1.8` branch at the pinned `%global
amd_commit` (`git clone --branch 1.8` then `git checkout <sha>`, or
`git fetch <sha>` — pick a shallow-friendly method). Firmware download
(`tools/info.json`) is unchanged in mechanism but now yields the npu3 blobs.

### 7. check-updates: track release branches, not the dead tag

The current step tracks `repos/amd/xdna-driver/tags` filtered to `N.N.N` — but
AMD has one tag and never bumps it, so xdna-driver auto-update is **already
dead**. Rewrite it to:
1. List branches (`repos/amd/xdna-driver/branches`), keep `^[0-9]+\.[0-9]+$`,
   take the highest (`sort -V`) that contains `drivers/accel`.
2. Read its XRT version (`src/CMake/settings.cmake` in the XRT submodule at that
   branch's commit) -> the `2.MINOR` to compare against the spec `Version`.
3. If the branch's HEAD commit differs from `%global amd_commit`, or the XRT
   version increased, bump (update `Version` and/or `amd_commit`).

### 8. README

Document, in the README (no `%post` hint): if you have a recent NPU (e.g. NPU3)
or newer firmware that the in-tree driver does not detect on kernel 7+, install
`xdna-driver-dkms` manually to get the 0.15 module.

## Risks to validate during implementation/testing

1. **Base package build with XRT 2.25** (the real one): XRT jumps 2.21 -> 2.25
   (4 minors). The key build options (`SKIP_KMOD`) still exist on 1.8, but the
   base RPM must be rebuilt and tested; expect possible `BuildRequires`/option
   tweaks.
2. **dkms.conf correctness**: AMD's is a CMake template; we reconstruct it.
   Validate end-to-end with a real `dkms install` producing a loadable
   `amdxdna.ko` 0.15.
3. **depmod precedence**: confirm `extra/`/`updates/` beats `kernel/` for
   `amdxdna` with the chosen `DEST_MODULE_LOCATION`.
4. **Build on real 6.x kernels**: validated on 7.0.10; test a low 6.x kernel
   (container) since that range is where the OOT module is the only driver.
5. **Behaviour after a kernel update**: if a future kernel breaks the OOT build,
   machines depending on it lose the NPU. Make `dkms` failures loud; document
   the fallback.

## Out of scope / future

- Per-distro in-tree boundary (openSUSE/RHEL may differ from Fedora's 7.0). Keep
  the current Fedora-tuned threshold for now.
