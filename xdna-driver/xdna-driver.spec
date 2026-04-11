%global debug_package %{nil}
%global __os_install_post %{nil}

Name:           xdna-driver
Version:        2.21.75
Release:        1%{?dist}
Summary:        AMD XDNA userspace driver, XRT libraries, NPU firmware, and DKMS kernel module

License:        Apache-2.0
URL:            https://github.com/amd/xdna-driver
Source0:        %{name}-%{version}.tar.gz

ExclusiveArch:  x86_64

BuildRequires:  cmake >= 3.19
BuildRequires:  make
BuildRequires:  gcc-c++
%if 0%{?suse_version}
BuildRequires:  pkg-config
%else
BuildRequires:  pkgconfig
%endif
BuildRequires:  git
BuildRequires:  boost-devel >= 1.74
%if !0%{?suse_version}
BuildRequires:  boost-static
%endif
BuildRequires:  libcurl-devel
BuildRequires:  libdrm-devel
BuildRequires:  libffi-devel
BuildRequires:  libuuid-devel
BuildRequires:  libyaml-devel
BuildRequires:  ncurses-devel
BuildRequires:  ocl-icd-devel
BuildRequires:  opencl-headers
%if 0%{?suse_version}
BuildRequires:  libopenssl-devel
%else
BuildRequires:  openssl-devel
%endif
BuildRequires:  protobuf-devel
%if !0%{?suse_version}
BuildRequires:  protobuf-compiler
%endif
BuildRequires:  python3-devel
BuildRequires:  rapidjson-devel
BuildRequires:  systemtap-sdt-devel
%if 0%{?suse_version}
BuildRequires:  libelf-devel
%else
BuildRequires:  elfutils-devel
%endif
BuildRequires:  gnutls-devel
BuildRequires:  json-glib-devel
%if 0%{?suse_version}
BuildRequires:  python-pybind11-common-devel
%else
BuildRequires:  pybind11-devel
%endif

Requires:       dkms
Requires:       %{name}-dkms = %{version}-%{release}

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
Kernel module source for the AMD XDNA2 NPU driver (amdxdna).
Automatically built for the installed kernel via DKMS.

%prep
%autosetup -n %{name}-%{version}

%build
%if 0%{?suse_version}
echo "=== BOOST DIAGNOSTIC ==="
rpm -qa | grep -i boost | sort
echo "=== CMAKE BOOST FILES ==="
find /usr/lib64/cmake /usr/share/cmake -name "*boost*" -o -name "*Boost*" 2>/dev/null | sort
echo "=== BOOST SO FILES ==="
find /usr/lib64 -name "libboost*.so*" 2>/dev/null | sort
echo "=== END DIAGNOSTIC ==="
%endif
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

# DKMS: install driver source to /usr/src/xrt-amdxdna-VERSION/
DKMS_SRC=%{buildroot}/usr/src/xrt-amdxdna-%{version}
install -d "${DKMS_SRC}/driver"
cp -r src/driver/amdxdna "${DKMS_SRC}/driver/amdxdna"

# dkms.conf
cat > "${DKMS_SRC}/dkms.conf" << 'DKMSEOF'
PACKAGE_NAME=xrt-amdxdna
PACKAGE_VERSION=%{version}
BUILD_EXCLUSIVE_KERNEL_MIN=6.10

MAKE="make -C driver/amdxdna KERNEL_SRC=${kernel_source_dir}"
CLEAN="make -C driver/amdxdna clean KERNEL_SRC=${kernel_source_dir}"

BUILT_MODULE_NAME[0]=amdxdna
BUILT_MODULE_LOCATION[0]="driver/amdxdna/build/driver/amdxdna"
DEST_MODULE_LOCATION[0]="/kernel/extras"

AUTOINSTALL="yes"

PRE_BUILD="./configure_kernel.sh"
DKMSEOF

install -m755 src/driver/tools/configure_kernel.sh \
    "${DKMS_SRC}/configure_kernel.sh"

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
if command -v dkms &>/dev/null; then
    dkms add -m xrt-amdxdna -v %{version} 2>&1 || :
    for kv in $(ls /lib/modules/ 2>/dev/null | sort -V); do
        if [ -d /lib/modules/${kv}/build ]; then
            dkms install -m xrt-amdxdna -v %{version} -k ${kv} 2>&1 || :
        fi
    done
fi

%preun dkms
if command -v dkms &>/dev/null; then
    dkms remove -m xrt-amdxdna -v %{version} --all 2>&1 || :
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

%changelog
* Sat Apr 11 2026 Alessandro Lattao <alessandro@lattao.com> - 2.21.75-1
- Initial packaging from amd/xdna-driver (replaces xrt-npu)
- Includes XRT userspace, AMD XDNA SHIM, NPU firmware, DKMS kernel module
