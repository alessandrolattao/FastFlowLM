# Design: ship the AMD out-of-tree amdxdna 0.15 driver as an optional DKMS upgrade

- Date: 2026-06-08
- Status: approved (brainstorming), pending implementation plan
- Scope: `xdna-driver` package only (the `-dkms` subpackage). No change to the
  base `xdna-driver` payload or to `fastflowlm`.

## Background

`flm validate` reports the loaded NPU driver as `amdxdna version: X.Y`. That
number is the DRM `major.minor` of the kernel module, not the version of our
`xdna-driver` RPM (2.21.75, which is the XRT userspace version).

On Fedora 44 (kernel 7.0.x) the loaded module is the **in-tree** driver shipped
by the kernel itself: `/lib/modules/<k>/kernel/drivers/accel/amdxdna/`. Its
version follows the kernel:

- in-tree, our kernel 7.0.10 -> **0.6** ("Support preemption")
- in-tree, mainline `master` -> **0.8** ("Support BO usage query")
- AMD out-of-tree repo (`drivers/accel/amdxdna`) -> **0.15**

The AMD repo develops ahead of mainline; 0.15 is higher than any in-tree
version. The `0.6 -> 0.15` delta (from the version-history comment in
`drivers/accel/amdxdna/amdxdna_pci_drv.c`) is:

| Ver | Adds |
|-----|------|
| 0.6 | Support preemption (where we are now) |
| 0.7 | power and utilization data |
| 0.8 | BO usage query |
| 0.9 | device type `AMDXDNA_DEV_TYPE_PF` |
| 0.10 | device type `AMDXDNA_DEV_TYPE_UMQ` |
| 0.11 | AIE coredump |
| 0.12 | **classic device type of NPU3** |
| 0.13 | AIE tile register/memory read/write |
| 0.14 | firmware log ioctls |
| 0.15 | firmware trace ioctls |

All of these are telemetry/diagnostics or **new device-type / hardware
support**. There is **no inference-performance feature** in this range. The
inference speed is determined by firmware + the proprietary NPU kernels
(`.xclbin`/`.so` fetched by `flm-fetch-kernels`) + `flm` itself, not by the DRM
driver.

### Why this matters

The in-tree driver on older/current kernels does not know newer NPU device
types (NPU3 added at 0.12) and may reject newer firmware protocol versions.
See amd/xdna-driver issues #1074 ("amdxdna module shipped with current linux
kernel is too old and not accepting new firmware") and #1219 ("firmware/driver
version mismatch prevents FastFlowLM on Strix Halo"). On machines newer than
ours, the in-tree 0.6/0.8 driver can fail to drive the NPU at all.

Our current setup works (`flm validate`: NPU on `/dev/accel/accel0`, FW
1.1.2.64, memlock infinity), so this is about **enabling newer hardware**, not
fixing our box.

## Goal

Make the **0.15 out-of-tree `amdxdna.ko`** available as an **optional DKMS
upgrade** for users whose NPU the in-tree driver cannot drive, without changing
behaviour for everyone whose in-tree driver already works.

## Non-goals

- No performance claims. The 0.15 delta has no inference-speed feature.
- Do not force the OOT module on systems where the in-tree driver works.
- No change to the base `xdna-driver` package (XRT, firmware, limits) or to
  `fastflowlm`.

## Key feasibility finding (validated)

The OOT `amdxdna.ko` (0.15, from `drivers/accel/amdxdna`) **compiles cleanly
out-of-tree against our running Fedora kernel 7.0.10-201.fc44** with no patches
and no extra build dependencies (gcc 16.1.1 + `kernel-devel` only). The build
runs with `-Werror`, so an API mismatch would be a hard build failure, not a
silent runtime problem; nothing needed patching on 7.0.

Portability across the 6.10 -> 7.x range is handled by AMD's
`drivers/accel/tools/configure_kernel.sh`, an autoconf-style feature-detection
script that probes the target kernel headers and generates `config_kernel.h`,
`-include`d into every translation unit. On 7.0.10 it correctly detected e.g.
`HAVE_7_0_kmalloc_ops`, `HAVE_6_17_drm_sched_job_init`,
`HAVE_7_0_amd_pmf_get_npu_data`; it is already aware of 7.0 and 7.2.

AMD also ships an official DKMS config for this tree at
`drivers/accel/CMake/config/dkms.conf.in`
(`BUILD_EXCLUSIVE_KERNEL_MIN=6.10`, `PRE_BUILD="./configure_kernel.sh"`,
`BUILT_MODULE_NAME=amdxdna`). We base our DKMS config on that instead of the
hand-written one we use for the legacy tree.

## Design decisions

### 1. Reuse `xdna-driver-dkms`, do not create a new subpackage

Per the "single solution" decision, we modify the existing `xdna-driver-dkms`
subpackage to build **0.15 from `drivers/accel/amdxdna`** instead of the legacy
`amdxdna_legacy.ko` from `src/driver/amdxdna`. One DKMS package, covering the
whole 6.10 -> 7.x range.

Note: the current `-dkms` builds the **legacy** tree (`src/driver/amdxdna`,
the "compatibility and bring-up" fallback module per AMD's README), not the
primary `amdxdna.ko`. Switching to `drivers/accel` also corrects that.

### 2. DKMS sources and build

- DKMS source becomes `drivers/accel/amdxdna` + `drivers/accel/tools/` (for
  `configure_kernel.sh`) + the `include/` headers it needs.
- `dkms.conf` based on AMD's `drivers/accel/CMake/config/dkms.conf.in`:
  - `PACKAGE_NAME=xrt-amdxdna`: keep the current DKMS package name for upgrade
    continuity (the existing `-dkms` already registers `xrt-amdxdna`, so reusing
    it keeps `--rpm_safe_upgrade` working across the switch).
  - `BUILD_EXCLUSIVE_KERNEL_MIN=6.10`.
  - **Raise the max**: today `BUILD_EXCLUSIVE_KERNEL_MAX=6.99` blocks kernel
    7+. Extend it to cover 7.x (or drop the upper bound) so a manual install on
    7+ actually builds.
  - `PRE_BUILD="./configure_kernel.sh"`, `BUILT_MODULE_NAME[0]=amdxdna`.
  - `BUILT_MODULE_LOCATION[0]` set to match the chosen build flow (in-place
    `M=<srcdir>` build vs AMD's `BUILD_ROOT_DIR` symlink flow). Validate the
    produced `.ko` path during implementation.

### 3. Install behaviour: conditional auto-pull, opt-in otherwise

The discriminator is **whether the kernel already has amdxdna in-tree**, not
the number 7.0 itself; on Fedora that boundary is kernel 7.0, so we keep the
existing conditional `Recommends`:

| Kernel | In-tree amdxdna? | OOT `-dkms` | NPU runs on |
|--------|------------------|-------------|-------------|
| < 7.0 | no | **auto-pulled** (Recommends) — only way to get a driver | OOT 0.15 |
| >= 7.0 | yes (0.6/0.8) | **opt-in** (manual install) | in-tree by default; OOT 0.15 if installed |

Rationale for not forcing it on every 7+ box: machines whose in-tree driver
already works gain **no useful feature** from 0.15 (no perf, no hardware they
lack) but would take on real risk — a module that compiles but regresses at
runtime, a DKMS build that breaks after a future kernel bump and silently drops
NPU support for anyone depending on the OOT module, or a firmware/driver
protocol mismatch. "Worst case it just doesn't compile" is the *lucky* case
(fallback to in-tree); the bad cases are worse. The conditional `Recommends`
already exists and is one line, so forcing it on all would not actually
simplify packaging — it would move complexity from the package (handled once)
to every user's runtime.

### 4. In-tree override + reversibility

- The OOT module installs into a modules dir that wins over the in-tree
  `kernel/` path in `depmod` ordering (`extra/` or `updates/`). Confirm the
  exact precedence with the chosen `DEST_MODULE_LOCATION` during
  implementation.
- **No permanent blacklist of the in-tree module.** On package removal, DKMS
  removes the OOT module, `depmod` re-runs, and the in-tree driver loads again
  on next boot. Removal must be a clean revert.

### 5. README

Document, in the README (no `%post` hint), when and how to install the OOT
driver manually on kernel 7+: "If you have a recent NPU (e.g. NPU3) or newer
firmware that the in-tree driver does not detect, install `xdna-driver-dkms`
manually to get the 0.15 module."

## Risks to validate during implementation/testing (not blockers)

1. **Firmware protocol match**: does 0.15 require a newer firmware protocol than
   the firmware we ship in the base package? We ship the firmware, so it should
   match, but verify (this is the failure mode behind #1074/#1219).
2. **depmod precedence**: confirm `extra/`/`updates/` actually wins over
   `kernel/` for `amdxdna` with the chosen install location.
3. **Build on real 6.x kernels**: validated on 7.0.10; test a low 6.x kernel
   (e.g. in a container) since that range is where the OOT module is the only
   option.
4. **Behaviour after a kernel update**: if a future kernel breaks the OOT
   build, machines depending on it lose the NPU. Document the fallback and make
   sure `dkms` failures are loud.

## Out of scope / future

- Per-distro in-tree boundary (openSUSE/RHEL may differ from Fedora's 7.0). Keep
  the current Fedora-tuned threshold for now.
