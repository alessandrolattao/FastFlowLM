%global debug_package %{nil}

# Upstream pin: amdxdna 0.15 lives only on the AMD '1.8' release branch (no tag).
# The build system clones this branch at this exact commit for reproducibility.
%global amd_branch 1.9
%global amd_commit c4052fc30322f8fa0a7f388f171bcb065d6dab6b

Name:           xdna-driver
Version:        2.26.0
Release:        2%{?dist}
Summary:        AMD XDNA userspace driver, XRT libraries, NPU firmware, and DKMS kernel module

License:        Apache-2.0
URL:            https://github.com/amd/xdna-driver
Source0:        %{name}-%{version}.tar.gz

ExclusiveArch:  x86_64

BuildRequires:  cmake >= 3.19
BuildRequires:  make
BuildRequires:  gcc-c++
BuildRequires:  pkgconfig
BuildRequires:  git
BuildRequires:  boost-devel >= 1.74
BuildRequires:  boost-static
BuildRequires:  libcurl-devel
BuildRequires:  libdrm-devel
BuildRequires:  libffi-devel
BuildRequires:  libuuid-devel
BuildRequires:  libyaml-devel
BuildRequires:  ncurses-devel
BuildRequires:  ocl-icd-devel
BuildRequires:  opencl-headers
BuildRequires:  openssl-devel
BuildRequires:  protobuf-devel
BuildRequires:  protobuf-compiler
BuildRequires:  python3-devel
BuildRequires:  rapidjson-devel
BuildRequires:  systemtap-sdt-devel
BuildRequires:  elfutils-devel
BuildRequires:  gnutls-devel
BuildRequires:  json-glib-devel
BuildRequires:  pybind11-devel

Requires:       dkms
# On kernel < 7 there is no in-tree amdxdna, so the -dkms module is the only
# driver available: the rich Recommends auto-pulls it there. On kernel 7+
# amdxdna is in-tree; the -dkms module (now the 0.15 OOT driver) still BUILDS
# and overrides the in-tree one, but we do NOT auto-pull it -- it is opt-in for
# users whose newer NPU (e.g. NPU3) the in-tree driver cannot drive (they run
# 'dnf install xdna-driver-dkms' manually). The "kernel" capability is provided
# by kernel-core on Fedora and RHEL/AlmaLinux/Rocky (+ EPEL).
Recommends:     (%{name}-dkms = %{version}-%{release} if kernel < 7.0)

%description
AMD XDNA userspace driver stack for Ryzen AI XDNA2 NPUs.

Includes:
  - XRT userspace libraries (libxrt_coreutil, libxrt_driver_xdna, etc.)
  - AMD XDNA SHIM (userspace NPU driver plugin)
  - NPU firmware for all supported XDNA2 devices (npu1/npu3/npu4/npu5)
  - DKMS kernel module (amdxdna) built automatically at install time

Required by fastflowlm. Kernel module requires kernel >= 6.10.

%package devel
Summary:        Development headers for xdna-driver
Requires:       %{name} = %{version}-%{release}

%description devel
Headers for building against the xdna-driver XRT libraries.
Used as BuildRequires for fastflowlm.

%package dkms
Summary:        DKMS source for the amdxdna kernel module
Requires:       dkms
Requires:       kernel-devel

%description dkms
Kernel module source for the AMD XDNA2 NPU driver (amdxdna), built via DKMS.

ONLY NEEDED ON KERNEL < 7. On Fedora 44 and newer (kernel 7.x) the amdxdna
driver is provided in-tree by the kernel itself; the main xdna-driver
package will not pull this subpackage in on those systems.

On RHEL/AlmaLinux/Rocky Linux, enable EPEL before installing this package:
  sudo dnf install epel-release
  sudo dnf install dkms kernel-devel

%prep
%autosetup -n %{name}-%{version}

%build
cmake -S . -B build \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/opt/xilinx/xrt \
    -DCMAKE_INSTALL_LIBDIR=lib64 \
    -DSKIP_KMOD=1 \
    -DBUILD_VXDNA=0 \
    -DXRT_ENABLE_DOCS=OFF \
    -DCMAKE_SKIP_RPATH=ON \
    -DCMAKE_CXX_STANDARD=17

make -j$(nproc) -C build

%install
make -C build DESTDIR=%{buildroot} install

# cmake installs XRT core libs to DESTDIR/bins/lib64 (hardcoded staging path).
# Move them to the canonical XRT prefix.
if [ -d %{buildroot}/bins ]; then
    cp -a %{buildroot}/bins/. %{buildroot}/opt/xilinx/xrt/
    rm -rf %{buildroot}/bins
fi

# Symlink lib -> lib64 for compatibility (FastFlowLM expects /opt/xilinx/xrt/lib)
ln -sf lib64 %{buildroot}/opt/xilinx/xrt/lib

# XRT headers (from submodule source tree - not installed by cmake in plugin mode)
install -d %{buildroot}/opt/xilinx/xrt/include
cp -r xrt/src/runtime_src/core/include/. %{buildroot}/opt/xilinx/xrt/include/

# Firmware (firmware/amdnpu/XX/npu.dev.sbin -> /usr/lib/firmware/amdnpu/XX/npu.dev.sbin)
find firmware/amdnpu -type f | while read f; do
    install -Dm644 "$f" "%{buildroot}/usr/lib/$f"
done

# DKMS: install the PRIMARY amdxdna 0.15 driver source (drivers/accel/amdxdna)
# to /usr/src/xrt-amdxdna-VERSION/. The repo layout MUST be preserved: the
# module's Kbuild prioritises the bundled uAPI header over the kernel's older
# in-tree one via "-iquote$(src)/../../../include/uapi", a path that only
# resolves when amdxdna sits at drivers/accel/amdxdna with include/ three
# levels up. A flat layout makes the compiler pick the kernel's in-tree
# amdxdna_accel.h (missing newer symbols, e.g. AMDXDNA_BO_SHARE) and the build
# fails. configure_kernel.sh (PRE_BUILD) feature-tests the target kernel and
# writes drivers/accel/amdxdna/config_kernel.h, making the module portable
# across 6.10 -> 7.x.
DKMS_SRC=%{buildroot}/usr/src/xrt-amdxdna-%{version}
install -d "${DKMS_SRC}/drivers/accel"
cp -r drivers/accel/amdxdna "${DKMS_SRC}/drivers/accel/amdxdna"
cp -r drivers/accel/tools   "${DKMS_SRC}/drivers/accel/tools"
cp -r include               "${DKMS_SRC}/include"

# dkms.conf. No BUILD_EXCLUSIVE_KERNEL_MAX: the 0.15 module builds on kernel 7+
# too and intentionally overrides the in-tree driver (DEST in updates/, which
# wins over kernel/ in depmod order). XDNA_HASH/XDNA_DRIVER_VERSION are passed
# so the module's Makefile does not shell out to git (absent in the DKMS tree).
cat > "${DKMS_SRC}/dkms.conf" << 'DKMSEOF'
PACKAGE_NAME="xrt-amdxdna"
PACKAGE_VERSION="%{version}"
BUILD_EXCLUSIVE_KERNEL_MIN="6.10"
AUTOINSTALL="yes"
PRE_BUILD="drivers/accel/tools/configure_kernel.sh"
MAKE[0]="make -C drivers/accel/amdxdna KERNEL_SRC=${kernel_source_dir} XDNA_HASH=%{amd_commit} XDNA_DRIVER_VERSION=%{version} modules"
CLEAN="make -C drivers/accel/amdxdna KERNEL_SRC=${kernel_source_dir} clean"
BUILT_MODULE_NAME[0]="amdxdna"
BUILT_MODULE_LOCATION[0]="drivers/accel/amdxdna"
DEST_MODULE_LOCATION[0]="/updates"
DKMSEOF

# Register lib64 with the dynamic linker
install -Dm644 /dev/null \
    %{buildroot}%{_sysconfdir}/ld.so.conf.d/xdna-driver.conf
echo "/opt/xilinx/xrt/lib64" \
    > %{buildroot}%{_sysconfdir}/ld.so.conf.d/xdna-driver.conf

# OpenCL ICD (if not already installed by cmake)
install -d %{buildroot}%{_sysconfdir}/OpenCL/vendors
[ -f %{buildroot}/etc/OpenCL/vendors/xilinx.icd ] || \
    echo "/opt/xilinx/xrt/lib64/libxilinxopencl.so.2" \
    > %{buildroot}%{_sysconfdir}/OpenCL/vendors/xilinx.icd

# Remove files not needed at runtime (XRT CLI tools, Python bindings, shell setup scripts)
rm -rf %{buildroot}/opt/xilinx/xrt/bin 2>/dev/null || true
rm -rf %{buildroot}/opt/xilinx/xrt/python 2>/dev/null || true
rm -rf %{buildroot}/opt/xilinx/xrt/share 2>/dev/null || true
rm -f %{buildroot}/opt/xilinx/xrt/setup.sh 2>/dev/null || true
rm -f %{buildroot}/opt/xilinx/xrt/setup.csh 2>/dev/null || true
rm -f %{buildroot}/opt/xilinx/xrt/setup.fish 2>/dev/null || true
rm -f %{buildroot}/opt/xilinx/xrt/version.json 2>/dev/null || true

# memlock limits for NPU buffer allocation
install -Dm644 /dev/null \
    %{buildroot}%{_sysconfdir}/security/limits.d/99-amdxdna.conf
printf '# Allow unlimited locked memory for AMD XDNA NPU buffer allocation\n* soft memlock unlimited\n* hard memlock unlimited\n' \
    > %{buildroot}%{_sysconfdir}/security/limits.d/99-amdxdna.conf

# dracut: exclude amdxdna from initramfs so it loads after rootfs is mounted
# (firmware lives on disk, not in initramfs - loading from initramfs causes ENOENT)
install -Dm644 /dev/null \
    %{buildroot}%{_sysconfdir}/dracut.conf.d/99-amdxdna.conf
printf '# amdxdna firmware lives on disk - exclude from initramfs, load after rootfs mount\nomit_drivers+=" amdxdna "\n' \
    > %{buildroot}%{_sysconfdir}/dracut.conf.d/99-amdxdna.conf

# depmod: make the OOT amdxdna (DKMS installs it under extra/) authoritative
# over the kernel's in-tree module via the documented "override" directive,
# instead of relying on depmod's default search order. Ships in -dkms and is
# removed with it, so removing the package cleanly reverts to the in-tree driver.
install -Dm644 /dev/null \
    %{buildroot}%{_sysconfdir}/depmod.d/99-amdxdna-oot.conf
printf 'override amdxdna * extra\n' \
    > %{buildroot}%{_sysconfdir}/depmod.d/99-amdxdna-oot.conf

%post
/sbin/ldconfig
echo ""
echo "xdna-driver installed."
echo "Memory lock limits have been set in /etc/security/limits.d/99-amdxdna.conf"
echo "Log out and back in (or reboot) for the limits to take effect."
echo ""

%postun
/sbin/ldconfig

%post dkms
if ! command -v dkms &>/dev/null; then
    echo ""
    echo "WARNING: dkms not found. The amdxdna kernel module will not be built."
    echo "On RHEL/AlmaLinux/Rocky Linux, enable EPEL first:"
    echo ""
    echo "  sudo dnf install epel-release"
    echo "  sudo dnf install dkms kernel-devel"
    echo ""
    echo "Then rebuild the module:"
    echo "  sudo dkms install xrt-amdxdna/%{version} -k \$(uname -r)"
    echo ""
    exit 0
fi
# Register the source tree with DKMS. Skip if already registered (upgrade
# path: the previous package version has the same source under the same
# name/version).
if ! dkms status -m xrt-amdxdna -v %{version} 2>/dev/null | grep -q xrt-amdxdna; then
    dkms add -m xrt-amdxdna -v %{version} --rpm_safe_upgrade 2>&1 || :
fi

%posttrans dkms
command -v dkms >/dev/null 2>&1 || exit 0

# Build only for the NEWEST installed in-range kernel (the one you will boot).
# DKMS builds inside the rpm transaction, which dnf5 runs with no live output,
# so building one kernel instead of every installed one keeps the install fast.
# Other and future kernels are built automatically by the dkms kernel-install
# hook (/usr/lib/kernel/install.d/40-dkms.install) when they get installed. The
# module builds on kernel >= 6.10 (BUILD_EXCLUSIVE_KERNEL_MIN, no upper bound);
# on kernel 7+ it overrides the in-tree amdxdna (installed under extra/, made
# authoritative by /etc/depmod.d/99-amdxdna-oot.conf).
# Read the driver version (e.g. 0.15) from the staged source so these messages
# stay correct when the bundled driver is bumped (0.16, ...).
DRV_VER=$(awk '/define AMDXDNA_DRIVER_MAJOR/{maj=$3} /define AMDXDNA_DRIVER_MINOR/{min=$3} END{if (maj != "") print maj"."min}' \
    /usr/src/xrt-amdxdna-%{version}/drivers/accel/amdxdna/amdxdna_pci_drv.c 2>/dev/null)
[ -n "$DRV_VER" ] || DRV_VER="out-of-tree"
# Pick the highest version-sorted in-range kernel that has build headers.
target=""
for kv in $(ls -1 /lib/modules/ 2>/dev/null | sort -V); do
    [ -d "/lib/modules/${kv}/build" ] || continue
    # Use cut, not bash prefix-trim: rpm collapses doubled percent signs
    # inside scriptlets, which would silently mangle the version split.
    maj=$(echo "$kv" | cut -d. -f1)
    min=$(echo "$kv" | cut -d. -f2)
    case "$maj" in *[!0-9]*|"") continue ;; esac
    case "$min" in *[!0-9]*|"") min=0 ;; esac
    { [ "$maj" -gt 6 ] || { [ "$maj" -eq 6 ] && [ "$min" -ge 10 ]; }; } || continue
    target="$kv"
done
built_any=0
if [ -n "$target" ]; then
    echo ""
    echo "xdna-driver-dkms: building the amdxdna ${DRV_VER} kernel module for ${target}."
    echo "This can take a few minutes; dnf will look idle until it finishes. Please wait..."
    if dkms install --force -m xrt-amdxdna -v %{version} -k "${target}"; then
        built_any=1
    else
        echo "WARNING: dkms build failed for ${target} - run: sudo dkms install xrt-amdxdna/%{version} -k ${target}"
    fi
fi

if [ "$built_any" -eq 1 ]; then
    echo ""
    echo "xdna-driver-dkms: amdxdna ${DRV_VER} module built and installed."
    echo ""
    echo "  >>> REBOOT REQUIRED to load the new driver:  sudo reboot"
    echo ""
    echo "  After rebooting, 'flm validate' should report 'amdxdna version: ${DRV_VER}'."
    echo ""
else
    echo "xdna-driver-dkms: no kernel >= 6.10 with headers found; nothing built."
fi

%preun dkms
command -v dkms >/dev/null 2>&1 || exit 0
# Only remove on final erase ($1 == 0), not on upgrade. --rpm_safe_upgrade
# is a second safety net: the new package's %post re-adds the same version.
if [ "$1" = "0" ]; then
    dkms remove -m xrt-amdxdna -v %{version} --all --rpm_safe_upgrade 2>&1 || :
fi

%files
%license xrt/LICENSE
%dir /opt/xilinx/xrt
/opt/xilinx/xrt/lib64/
/opt/xilinx/xrt/lib
%config(noreplace) %{_sysconfdir}/OpenCL/vendors/xilinx.icd
%config(noreplace) %{_sysconfdir}/ld.so.conf.d/xdna-driver.conf
%config(noreplace) %{_sysconfdir}/security/limits.d/99-amdxdna.conf
/usr/lib/firmware/amdnpu/

%files devel
/opt/xilinx/xrt/include/

%files dkms
/usr/src/xrt-amdxdna-%{version}/
%config(noreplace) %{_sysconfdir}/dracut.conf.d/99-amdxdna.conf
%config(noreplace) %{_sysconfdir}/depmod.d/99-amdxdna-oot.conf

%changelog
* Thu Aug 20 2026 Alessandro Lattao <alessandro@lattao.com> - 2.26.0-2
- Rebuild against the amd-xdna branch at commit c4052fc30322

* Wed Aug 19 2026 Alessandro Lattao <alessandro@lattao.com> - 2.26.0-1
- Update to 2.26.0

* Thu Aug 6 2026 Alessandro Lattao <alessandro@lattao.com> - 2.25.0-10
- Rebuild against the amd-xdna branch at commit 31c01f2019e7

* Tue Aug 4 2026 Alessandro Lattao <alessandro@lattao.com> - 2.25.0-9
- Rebuild against the amd-xdna branch at commit c0c42d04abe3

* Thu Jul 23 2026 Alessandro Lattao <alessandro@lattao.com> - 2.25.0-8
- Rebuild against the amd-xdna branch at commit 733416742793

* Sat Jul 18 2026 Alessandro Lattao <alessandro@lattao.com> - 2.25.0-7
- Rebuild against the amd-xdna branch at commit f07c40c56bec

* Fri Jul 17 2026 Alessandro Lattao <alessandro@lattao.com> - 2.25.0-6
- Rebuild against the amd-xdna branch at commit 814132d15f67

* Mon Jul 13 2026 Alessandro Lattao <alessandro@lattao.com> - 2.25.0-5
- Rebuild against the amd-xdna 1.8 branch at commit 485f56cee665 (was
  039c0d35); the branch advanced without a version change.
- Drop the stray auto-update changelog entries that re-bumped 2.25.0-1 on
  every upstream branch commit without incrementing the release. The
  check-updates workflow now records a single rebuild entry and increments
  the release instead of resetting it to -1.

* Tue Jun 09 2026 Alessandro Lattao <alessandro@lattao.com> - 2.25.0-4
- Add /etc/depmod.d/99-amdxdna-oot.conf with "override amdxdna * extra" so the
  out-of-tree module is authoritative over the kernel's in-tree amdxdna via the
  documented depmod override directive, instead of relying on the default search
  order. Removed with -dkms, so removal cleanly reverts to the in-tree driver.
- %%posttrans dkms: build only the newest in-range installed kernel instead of
  every installed kernel (Fedora kmod guidance). dkms's kernel-install hook
  builds the rest when they are installed. Faster install, shorter "idle" window.
- Drop openSUSE BuildRequires conditionals (Fedora/RHEL only).

* Mon Jun 08 2026 Alessandro Lattao <alessandro@lattao.com> - 2.25.0-3
- %%posttrans dkms: drop the per-kernel "compiling ..." lines. dnf5 buffers
  scriptlet output and prints it all at the end, so the per-kernel progress was
  just noise dumped at once. Keep a single upfront "building, please wait (dnf
  will look idle)" notice and the final reboot reminder.

* Mon Jun 08 2026 Alessandro Lattao <alessandro@lattao.com> - 2.25.0-2
- %%posttrans dkms: print an upfront "compiling, please wait" notice (building
  the module for every installed kernel can take minutes with no output and
  looks like a hang), a clearer per-kernel line, and a prominent reboot
  reminder. The driver version shown is read from the staged source
  (AMDXDNA_DRIVER_MAJOR/MINOR), not hardcoded, so it stays correct on bumps.
- Release bump so the updated scriptlet ships under a distinct NVR (the prior
  same-NVR rebuild was not picked up by dnf reinstall).

* Mon Jun 08 2026 Alessandro Lattao <alessandro@lattao.com> - 2.25.0-1
- Bump to the AMD 1.8 release branch (XRT 2.25, amdxdna driver 0.15, npu3
  firmware), pinned to commit 039c0d35. The -dkms subpackage now builds the
  primary drivers/accel amdxdna.ko (0.15) instead of the legacy module.

* Mon Jun 08 2026 Alessandro Lattao <alessandro@lattao.com> - 2.21.75-5
- %%posttrans dkms: fix the kernel-version split that skipped every kernel,
  so the module was never built on kernel 6.x. The bash prefix-trim used to
  parse the version was mangled by rpm scriptlet macro expansion (doubled
  percent signs collapse to one); split the major/minor fields with 'cut'
  instead. This bug predates the -4 scriptlet rework.

* Mon Jun 08 2026 Alessandro Lattao <alessandro@lattao.com> - 2.21.75-4
- %%posttrans dkms: drop 'dracut -f --regenerate-all'. It could regenerate a
  broken initramfs for the running kernel (missing drivers -> no boot) and was
  pointless: amdxdna is omitted from the initramfs by design (omit_drivers).
- Drop the '%%global __os_install_post %%{nil}' override (keep only
  debug_package %%{nil}) so the XRT libraries ship stripped instead of carrying
  full DWARF debug info (libxrt_coreutil.so: 46 MB -> ~3 MB).
- Harden DKMS scriptlets: add --rpm_safe_upgrade to 'dkms add'/'dkms remove',
  only remove on final erase ($1 == 0) instead of on every upgrade, and filter
  the %%posttrans build loop on the full BUILD_EXCLUSIVE range (6.10 - 6.x).

* Wed May 20 2026 Alessandro Lattao <alessandro@lattao.com> - 2.21.75-3
- dkms.conf: drop deprecated CLEAN= directive (DKMS now runs make clean
  automatically and warns if CLEAN= is set)
- %%post dkms: check dkms status before dkms add so the "DKMS tree
  already contains" error is not printed on package upgrades
- %%posttrans dkms: filter installed kernels to those < 7.0 (the OOT
  module's BUILD_EXCLUSIVE range) before invoking DKMS. If no kernel
  needs the OOT module (kernel 7+ has amdxdna in-tree), exit cleanly
  with an explanatory message instead of printing a fake
  "Done! Reboot to activate" after three failed builds

* Wed May 20 2026 Alessandro Lattao <alessandro@lattao.com> - 2.21.75-2
- Make xdna-driver-dkms a conditional weak dependency of the main package
  using a boolean Recommends: (xdna-driver-dkms if kernel < 7.0)
- On kernel 7+ the amdxdna driver is provided in-tree, so the -dkms
  subpackage is no longer pulled in automatically (works on Fedora/RHEL
  via kernel-core and on openSUSE via kernel-default, both of which
  Provide "kernel = <ver>")

* Sat Apr 11 2026 Alessandro Lattao <alessandro@lattao.com> - 2.21.75-1
- Initial packaging from amd/xdna-driver (replaces xrt-npu)
- Includes XRT userspace, AMD XDNA SHIM, NPU firmware, DKMS kernel module
