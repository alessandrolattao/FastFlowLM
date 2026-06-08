# amdxdna 0.15 OOT DKMS upgrade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bump the `xdna-driver` package to the AMD `1.8` release so it ships the amdxdna 0.15 driver source, npu3 firmware, and XRT 2.25, and make the `-dkms` subpackage build the 0.15 `amdxdna.ko` as an optional override of the in-tree driver.

**Architecture:** One spec (`xdna-driver/xdna-driver.spec`) drives a base package (XRT + firmware + SHIM) and three subpackages (`-devel`, `-dkms`). The source tarball is produced by the repo `Makefile`/`.copr/Makefile` by cloning AMD's repo. We pin to the `1.8` branch at a fixed commit (no usable tag exists), version the package by XRT version (`2.25.x` > current `2.21.75`, so no Epoch), switch the `-dkms` tree from the legacy `src/driver/amdxdna` to the primary `drivers/accel/amdxdna` (0.15), and rewrite `check-updates` to track release branches instead of the dead tag.

**Tech Stack:** RPM spec (rpmbuild/mock), DKMS, GNU Make, GitHub Actions, `gh` CLI, kernel out-of-tree module build.

**Reference:** design spec at `docs/superpowers/specs/2026-06-08-amdxdna-oot-dkms-design.md`. Pinned upstream: `amd/xdna-driver` branch `1.8`, commit `039c0d3528a340266203c5b48f41ed61262af67b`.

**Test environment warning:** Do NOT `dkms install` the OOT module on the developer's own machine — it would replace the working in-tree driver. All install/load tests run in a throwaway container or VM (e.g. `mock` for RPM builds, a Fedora 44 container for DKMS/`depmod` checks). The developer's box is npu4 (FW 1.1.2.64) and already works on the in-tree 0.6 driver.

---

### Task 1: Spike — produce a working `dkms.conf` for the `drivers/accel` tree

**Goal:** Determine the exact `MAKE` / `BUILT_MODULE_LOCATION` / `DEST_MODULE_LOCATION` values that make `dkms build` produce a loadable `amdxdna.ko` 0.15. These values feed Task 4. Work in a scratch dir, not the repo.

**Files:**
- Scratch only (e.g. `/tmp/dkms-spike/`). Produces: a validated `dkms.conf` snippet pasted into this task's checkbox notes for Task 4 to consume.

- [ ] **Step 1: Clone the pinned source**

```bash
cd /tmp/dkms-spike && rm -rf xdna
git clone --depth 1 --no-recurse-submodules --branch 1.8 https://github.com/amd/xdna-driver xdna
cd xdna && git fetch --depth 1 origin 039c0d3528a340266203c5b48f41ed61262af67b && git checkout 039c0d3528a340266203c5b48f41ed61262af67b
```

- [ ] **Step 2: Read the module Makefile to learn its targets/vars**

Run: `sed -n '1,80p' drivers/accel/amdxdna/Makefile`
Expected: a Kbuild-wrapper Makefile with a `modules` target honoring `KERNEL_SRC` (or `-C <kdir> M=<dir>`) and `OFT_CONFIG_AMDXDNA_PCI`/`OFT_CONFIG_AMDXDNA_OF` switches. Note the exact variable names.

- [ ] **Step 3: Stage a DKMS source tree and write a candidate `dkms.conf`**

```bash
SRC=/var/lib/dkms-spike-src; sudo rm -rf "$SRC"; sudo mkdir -p "$SRC"
sudo cp -r drivers/accel/amdxdna "$SRC/amdxdna"
sudo cp -r drivers/accel/tools "$SRC/tools"
sudo cp -r include "$SRC/include"
sudo cp drivers/accel/tools/configure_kernel.sh "$SRC/configure_kernel.sh"
sudo tee "$SRC/dkms.conf" >/dev/null <<'EOF'
PACKAGE_NAME=xrt-amdxdna
PACKAGE_VERSION=2.25.0
BUILD_EXCLUSIVE_KERNEL_MIN=6.10
MAKE[0]="make -C amdxdna KERNEL_SRC=${kernel_source_dir} OFT_CONFIG_AMDXDNA_PCI=y OFT_CONFIG_AMDXDNA_OF=n modules"
BUILT_MODULE_NAME[0]=amdxdna
BUILT_MODULE_LOCATION[0]="amdxdna"
DEST_MODULE_LOCATION[0]="/updates"
AUTOINSTALL="yes"
PRE_BUILD="./configure_kernel.sh"
EOF
```

- [ ] **Step 4: Register and build via DKMS against the running kernel**

```bash
sudo cp -r "$SRC" /usr/src/xrt-amdxdna-2.25.0
sudo dkms add    -m xrt-amdxdna -v 2.25.0
sudo dkms build  -m xrt-amdxdna -v 2.25.0 -k "$(uname -r)"
```
Expected: build completes; `.ko` at `/var/lib/dkms/xrt-amdxdna/2.25.0/$(uname -r)/x86_64/module/amdxdna.ko`.
If `MAKE`/`BUILT_MODULE_LOCATION` are wrong, dkms reports "Module build failed" or "did not produce a built module"; adjust paths using the Makefile facts from Step 2 and re-run.

- [ ] **Step 5: Confirm it is the 0.15 module**

Run: `sudo dkms status -m xrt-amdxdna` then `modinfo /var/lib/dkms/xrt-amdxdna/2.25.0/$(uname -r)/x86_64/module/amdxdna.ko | grep -E 'filename|vermagic'`
Expected: `installed`/`built`, vermagic matches the running kernel.

- [ ] **Step 6: Clean up the spike (do NOT install)**

```bash
sudo dkms remove -m xrt-amdxdna -v 2.25.0 --all || true
sudo rm -rf /usr/src/xrt-amdxdna-2.25.0 /var/lib/dkms-spike-src /tmp/dkms-spike
```
Record the final working `dkms.conf` (exact `MAKE`/`BUILT_MODULE_LOCATION`/`DEST_MODULE_LOCATION`) in this task's notes for Task 4.

- [ ] **Step 7: Commit** (nothing to commit — spike only; note results in the PR description)

---

### Task 2: Build system — clone the `1.8` branch at a pinned commit

**Files:**
- Modify: `Makefile` (the `build-srpm` define)
- Modify: `.copr/Makefile`
- Modify: `xdna-driver/xdna-driver.spec` (add the pin global)

- [ ] **Step 1: Add the commit pin to the spec**

In `xdna-driver/xdna-driver.spec`, directly under the existing `%global` block near the top, add:

```spec
# Upstream pin: amdxdna 0.15 lives only on the AMD '1.8' release branch (no tag).
%global amd_branch 1.8
%global amd_commit 039c0d3528a340266203c5b48f41ed61262af67b
```

- [ ] **Step 2: Change `Makefile` clone logic for xdna-driver**

In `Makefile`, inside `define build-srpm`, replace the xdna-driver branch derivation and clone. Currently:

```make
	if [ "$$PKG" = "xdna-driver" ]; then \
	    REPO="https://github.com/amd/xdna-driver"; \
	    BRANCH="$$VER"; \
```

Change the clone so xdna-driver fetches the pinned commit on branch `1.8`. Replace the `git clone --recurse-submodules --branch $$BRANCH --depth 1 $$REPO $$PKG-$$VER` path with logic that, for xdna-driver, reads `amd_commit`/`amd_branch` from the spec and does:

```make
	    AMD_BRANCH=$$(awk '/^%global amd_branch/{print $$3}' "$$SPEC"); \
	    AMD_COMMIT=$$(awk '/^%global amd_commit/{print $$3}' "$$SPEC"); \
	    git clone --recurse-submodules --branch "$$AMD_BRANCH" $$REPO $$PKG-$$VER; \
	    git -C $$PKG-$$VER checkout "$$AMD_COMMIT"; \
	    git -C $$PKG-$$VER submodule update --init --recursive; \
```

(fastflowlm keeps `--branch v$$VER --depth 1`.) Note: drop `--depth 1` for the xdna checkout-by-SHA path, or fetch the SHA explicitly, because a shallow `--branch` clone may not contain an arbitrary commit.

- [ ] **Step 3: Mirror the same change in `.copr/Makefile`**

Apply the identical branch+commit clone logic to `.copr/Makefile` (it has its own copy of the clone block and reads the spec via `$(spec)`).

- [ ] **Step 4: Verify the tarball contains the new tree and firmware**

Run:
```bash
make srpm-xdna 2>&1 | tail -20
```
Expected: SRPM written to `out/xdna-driver-*.src.rpm`. Then inspect the embedded tarball:
```bash
rpm2cpio out/xdna-driver-2.25.0-*.src.rpm | cpio -t 2>/dev/null | grep -m1 'xdna-driver-2.25.0.tar.gz'
```
(Full content check happens in Task 6's build.) Expected: the source tarball is present.

- [ ] **Step 5: Commit**

```bash
git add Makefile .copr/Makefile xdna-driver/xdna-driver.spec
git commit -m "build: pin xdna-driver source to AMD 1.8 branch at fixed commit"
```

---

### Task 3: Bump package version to 2.25.0 (XRT scheme, no Epoch)

**Files:**
- Modify: `xdna-driver/xdna-driver.spec` (`Version`, `Release`, `%changelog`)

- [ ] **Step 1: Set version and release**

In `xdna-driver/xdna-driver.spec`:
```spec
Version:        2.25.0
Release:        1%{?dist}
```
Do NOT add `Epoch` (2.25.0 > 2.21.75 already sorts as an upgrade).

- [ ] **Step 2: Add a changelog entry**

Prepend under `%changelog`:
```spec
* Mon Jun 08 2026 Alessandro Lattao <alessandro@lattao.com> - 2.25.0-1
- Bump to the AMD 1.8 release branch (XRT 2.25, amdxdna driver 0.15, npu3
  firmware), pinned to commit 039c0d35. The -dkms subpackage now builds the
  primary drivers/accel amdxdna.ko (0.15) instead of the legacy module.
```

- [ ] **Step 3: Verify rpm sees it as an upgrade over 2.21.75**

Run: `rpmdev-vercmp 2.21.75-2 2.25.0-1; echo "exit=$?"`
Expected: prints that `2.25.0-1` is newer (`rpmdev-vercmp` exits 11 when the first is older / 12 when newer — confirm 2.25.0-1 is reported newer).

- [ ] **Step 4: Commit**

```bash
git add xdna-driver/xdna-driver.spec
git commit -m "xdna-driver 2.25.0-1: bump to AMD 1.8 (XRT 2.25, amdxdna 0.15)"
```

---

### Task 4: Switch `-dkms` to build amdxdna 0.15 from `drivers/accel`

**Files:**
- Modify: `xdna-driver/xdna-driver.spec` (the `%install` DKMS staging block, lines ~143-168, and `%files dkms`)

- [ ] **Step 1: Replace the DKMS source staging**

In `%install`, the current block copies the legacy tree:
```spec
DKMS_SRC=%{buildroot}/usr/src/xrt-amdxdna-%{version}
install -d "${DKMS_SRC}/driver"
cp -r src/driver/amdxdna "${DKMS_SRC}/driver/amdxdna"
cp -r src/include "${DKMS_SRC}/include"
```
Replace with the primary tree:
```spec
DKMS_SRC=%{buildroot}/usr/src/xrt-amdxdna-%{version}
install -d "${DKMS_SRC}"
cp -r drivers/accel/amdxdna "${DKMS_SRC}/amdxdna"
cp -r drivers/accel/tools  "${DKMS_SRC}/tools"
cp -r include              "${DKMS_SRC}/include"
```

- [ ] **Step 2: Write the new `dkms.conf` (values from Task 1 spike)**

Replace the heredoc with the validated config from Task 1. Baseline (adjust `MAKE`/`BUILT_MODULE_LOCATION` to the Task 1 result):
```spec
cat > "${DKMS_SRC}/dkms.conf" << 'DKMSEOF'
PACKAGE_NAME=xrt-amdxdna
PACKAGE_VERSION=%{version}
BUILD_EXCLUSIVE_KERNEL_MIN=6.10
MAKE[0]="make -C amdxdna KERNEL_SRC=${kernel_source_dir} OFT_CONFIG_AMDXDNA_PCI=y OFT_CONFIG_AMDXDNA_OF=n modules"
BUILT_MODULE_NAME[0]=amdxdna
BUILT_MODULE_LOCATION[0]="amdxdna"
DEST_MODULE_LOCATION[0]="/updates"
AUTOINSTALL="yes"
PRE_BUILD="./configure_kernel.sh"
DKMSEOF

install -m755 drivers/accel/tools/configure_kernel.sh "${DKMS_SRC}/configure_kernel.sh"
```
Key changes vs today: source dir is `drivers/accel`, **`BUILD_EXCLUSIVE_KERNEL_MAX` is removed** (build on 7+ too), `DEST_MODULE_LOCATION` is `/updates` (wins over in-tree `kernel/` in depmod order).

- [ ] **Step 3: Keep `%files dkms` pointed at the source tree**

Confirm `%files dkms` still lists `/usr/src/xrt-amdxdna-%{version}/` and the dracut conf. No path change needed (the dir name is unchanged).

- [ ] **Step 4: Verify the spec parses and stages the right tree**

Run: `rpmspec -P xdna-driver/xdna-driver.spec >/dev/null && echo OK`
Expected: `OK` (no parse errors). The end-to-end DKMS build is validated in Task 7.

- [ ] **Step 5: Commit**

```bash
git add xdna-driver/xdna-driver.spec
git commit -m "xdna-driver-dkms: build amdxdna 0.15 from drivers/accel, override in-tree"
```

---

### Task 5: Confirm conditional install behaviour (auto < 7.0, opt-in >= 7.0)

**Files:**
- Inspect/Modify: `xdna-driver/xdna-driver.spec` (the `Recommends` line and `%post dkms`/`%posttrans dkms`)

- [ ] **Step 1: Verify the conditional Recommends is intact**

Run: `grep -n 'Recommends' xdna-driver/xdna-driver.spec`
Expected: `Recommends: (%{name}-dkms = %{version}-%{release} if kernel < 7.0)`. Keep it — auto-pull below 7.0, opt-in at/above 7.0.

- [ ] **Step 2: Drop the obsolete 6.99 range filter from `%posttrans dkms`**

The `%posttrans dkms` loop currently filters kernels to `maj==6 && min>=10` (matching the old `BUILD_EXCLUSIVE_KERNEL_MAX=6.99`). Since the module now builds on 7+ too, widen it to "kernel >= 6.10" (`maj>6`, or `maj==6 && min>=10`) so a manual install on a 7.x box actually builds. Update the comment that says "amdxdna is in-tree on kernel 7+" to reflect that we now intentionally override it when the package is installed.

- [ ] **Step 3: Verify the loop logic**

Run: `awk '/%posttrans dkms/,/^%preun/' xdna-driver/xdna-driver.spec`
Expected: the kernel filter admits 7.x kernels (no upper bound at 6.99).

- [ ] **Step 4: Commit**

```bash
git add xdna-driver/xdna-driver.spec
git commit -m "xdna-driver-dkms: build OOT module on kernel 7+ too (drop 6.99 ceiling)"
```

---

### Task 6: Rewrite `check-updates` to track release branches

**Files:**
- Modify: `.github/workflows/check-updates.yml` (the "Check xdna-driver latest tag" step)

- [ ] **Step 1: Replace the tag query with a branch+XRT query**

Replace the `LATEST=$(gh api repos/amd/xdna-driver/tags ...)` block with logic that:
```bash
# highest numeric release branch that has drivers/accel
BRANCH=$(gh api repos/amd/xdna-driver/branches --paginate --jq '.[].name' \
  | grep -E '^[0-9]+\.[0-9]+$' | sort -V | tac \
  | while read b; do
      if gh api "repos/amd/xdna-driver/contents/drivers/accel?ref=$b" >/dev/null 2>&1; then echo "$b"; break; fi
    done)
COMMIT=$(gh api "repos/amd/xdna-driver/commits/$BRANCH" --jq '.sha')
# XRT minor from the submodule's settings.cmake at that branch
XRT_SHA=$(gh api "repos/amd/xdna-driver/contents/xrt?ref=$BRANCH" --jq '.sha')
XRT_MIN=$(gh api "repos/Xilinx/XRT/contents/src/CMake/settings.cmake?ref=$XRT_SHA" \
  --jq '.content' | base64 -d | awk '/set\(XRT_VERSION_MINOR/{gsub(/[^0-9]/,"",$2);print $2}')
LATEST="2.${XRT_MIN}.0"
CUR_COMMIT=$(awk '/^%global amd_commit/{print $3}' xdna-driver/xdna-driver.spec)
CURRENT=$(awk '/^Version:/{print $2}' xdna-driver/xdna-driver.spec)
if [ "$LATEST" != "$CURRENT" ] || [ "$COMMIT" != "$CUR_COMMIT" ]; then echo "updated=true" >> "$GITHUB_OUTPUT"; fi
echo "latest=$LATEST" >> "$GITHUB_OUTPUT"; echo "commit=$COMMIT" >> "$GITHUB_OUTPUT"; echo "branch=$BRANCH" >> "$GITHUB_OUTPUT"
```

- [ ] **Step 2: Update the spec from the workflow**

The "Update xdna-driver spec" step must set `Version`, `Release: 1%{?dist}`, `%global amd_branch`, `%global amd_commit`, and prepend a changelog line. Since `make bump-xdna` only knows about `Version`/tag, add a small inline `sed` in the workflow for `amd_branch`/`amd_commit`, or extend `bump-xdna` to accept `BRANCH=`/`COMMIT=`. Implement the `sed` inline:
```bash
sed -i "s|^%global amd_branch.*|%global amd_branch ${BRANCH}|" xdna-driver/xdna-driver.spec
sed -i "s|^%global amd_commit.*|%global amd_commit ${COMMIT}|" xdna-driver/xdna-driver.spec
make bump-xdna VER="${LATEST}"
```

- [ ] **Step 3: Lint the workflow YAML**

Run: `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/check-updates.yml')); print('YAML OK')"`
Expected: `YAML OK`.

- [ ] **Step 4: Dry-run the detection logic locally**

Run the Step 1 snippet in a shell (with `GH_TOKEN` set) and confirm: `BRANCH=1.8`, `LATEST=2.25.0`, `COMMIT=039c0d35...`.
Expected: matches the pinned values currently in the spec (so `updated` would be false right now — correct, we just pinned it).

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/check-updates.yml
git commit -m "ci: track AMD release branches (not the dead tag) for xdna-driver updates"
```

---

### Task 7: README + end-to-end build/install validation

**Files:**
- Modify: `README.md`
- Test: throwaway Fedora 44 container / `mock`

- [ ] **Step 1: Document the opt-in OOT module in the README**

Add a section to `README.md`:
```markdown
## Newer NPUs (NPU3) on kernel 7+

On kernel 7+ the package uses the kernel's in-tree `amdxdna` driver by default.
If you have a recent NPU (e.g. NPU3) or newer firmware that the in-tree driver
does not detect, install the out-of-tree 0.15 module manually:

    sudo dnf install xdna-driver-dkms

Remove it to revert to the in-tree driver:

    sudo dnf remove xdna-driver-dkms
```

- [ ] **Step 2: Build the SRPM**

Run: `make srpm-xdna 2>&1 | tail -5`
Expected: `out/xdna-driver-2.25.0-1.*.src.rpm` produced.

- [ ] **Step 3: Build the base + subpackages in mock (validates XRT 2.25 builds)**

Run: `mock -r fedora-44-x86_64 --rebuild out/xdna-driver-2.25.0-1.*.src.rpm 2>&1 | tail -30`
Expected: build succeeds; RPMs for `xdna-driver`, `-devel`, `-dkms` produced. If XRT 2.25 needs extra `BuildRequires`, add them to the spec and rebuild (this is risk #1 from the spec).

- [ ] **Step 4: DKMS build + module identity in a container (NOT on the host)**

In a Fedora 44 container with `kernel-devel` matching a target kernel, install the built `-dkms` RPM and verify:
```bash
dkms status -m xrt-amdxdna           # -> built/installed for the target kernel
modinfo $(modinfo -n amdxdna) | grep -E 'filename|vermagic'   # OOT path under updates/
```
Then confirm version 0.15 from the source: `grep AMDXDNA_DRIVER_MINOR /usr/src/xrt-amdxdna-2.25.0/amdxdna/amdxdna_pci_drv.c` -> `15`.
Expected: module builds, lands in `updates/` (wins over `kernel/`).

- [ ] **Step 5: depmod precedence check (container)**

Run: `depmod -a && modprobe --resolve-alias amdxdna; modinfo amdxdna | grep filename`
Expected: filename resolves to the `updates/` OOT path, not the in-tree `kernel/drivers/accel/` path. (Risk #3.)

- [ ] **Step 6: Reversibility check (container)**

Run: `dnf remove -y xdna-driver-dkms && depmod -a && modinfo amdxdna | grep filename`
Expected: filename resolves back to the in-tree `kernel/` path (clean revert, no leftover blacklist).

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs: document opt-in OOT amdxdna 0.15 module for newer NPUs"
```

---

## Self-review notes

- Spec coverage: ref pin (T2), version/no-Epoch (T3), `-dkms` from drivers/accel + no MAX + override (T4), conditional install (T5), build-on-7+ (T5), check-updates rewrite (T6), README (T7), base-build/dkms/depmod/reversibility risks (T7). configure_kernel.sh portability is exercised by T1/T7.
- Open dependency: Task 4's `dkms.conf` values come from Task 1's spike — do Task 1 first.
- Not covered by automated tests (manual/container only): real 6.x-kernel build (spec risk #4) and post-kernel-update behaviour (risk #5) — call these out in the PR for manual follow-up rather than blocking the merge.
