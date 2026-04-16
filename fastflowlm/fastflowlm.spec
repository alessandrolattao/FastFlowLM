%global debug_package %{nil}
%global __os_install_post %{nil}
%global _prefix /opt/fastflowlm

# Minimum expected NPU driver version (passed to CMake)
%global npu_version 32.0.203.304

Name:           fastflowlm
Version:        0.9.39
Release:        1%{?dist}
Summary:        Run LLMs on AMD Ryzen AI NPUs - runtime and CLI

# Open-source (MIT) portion only. Proprietary NPU kernel binaries are NOT
# included in this package; they are downloaded at runtime via
# flm-fetch-kernels from the official FastFlowLM release.
License:        MIT
URL:            https://github.com/FastFlowLM/FastFlowLM
Source0:        %{name}-%{version}.tar.gz
Source1:        flm-fetch-kernels

ExclusiveArch:  x86_64

BuildRequires:  cmake >= 3.22
%if 0%{?suse_version}
BuildRequires:  ninja
%else
BuildRequires:  ninja-build
%endif
BuildRequires:  gcc-c++
%if 0%{?suse_version}
BuildRequires:  pkg-config
%else
BuildRequires:  pkgconfig
%endif
BuildRequires:  git
%if 0%{?suse_version}
BuildRequires:  ffmpeg-devel
%else
BuildRequires:  ffmpeg-free-devel
%endif
BuildRequires:  boost-devel
BuildRequires:  libcurl-devel
BuildRequires:  libdrm-devel
%if 0%{?suse_version}
BuildRequires:  fftw3-devel
%else
BuildRequires:  fftw-devel
%endif
BuildRequires:  readline-devel
BuildRequires:  libuuid-devel
BuildRequires:  cargo
BuildRequires:  rust
BuildRequires:  xdna-driver-devel

# Runtime: serve XRT per linkare xrt_coreutil
Requires:       xdna-driver

%description
FastFlowLM (FLM) runs large language models on AMD Ryzen AI XDNA2 NPUs
with a simple Ollama-like CLI interface. Purpose-built for NPU inference:
faster and over 10x more power-efficient than GPU-based runtimes.

Supports all Ryzen AI chips with XDNA2 NPUs (Strix, Strix Halo, Kraken,
Gorgon Point).

REQUIREMENTS:
  - AMD Ryzen AI CPU with XDNA2 NPU (Strix/Kraken/Gorgon generation)
  - xdna-driver package (installs XRT, firmware and kernel module via DKMS)
  - NPU firmware version >= 1.1.0.0
  - Unlimited memlock limit (add to /etc/security/limits.conf:
      *  soft  memlock  unlimited
      *  hard  memlock  unlimited)

AFTER INSTALL: run 'flm-fetch-kernels' to download the proprietary NPU
kernel binaries from the official FastFlowLM release. Internet access
to GitHub is required for this step.

%prep
%autosetup -n %{name}-%{version}

%build
cd src
cmake --preset linux-default \
    -DXRT_INCLUDE_DIR=/opt/xilinx/xrt/include \
    -DXRT_LIB_DIR=/opt/xilinx/xrt/lib \
    -DFLM_VERSION=%{version} \
    -DNPU_VERSION=%{npu_version}

cmake --build build -j$(nproc)

%install
cd src
# cmake install(CODE) creates /usr/local/bin/flm outside DESTDIR (ignores env).
# Pre-create it inside buildroot so the symlink lands there; ignore any failure.
mkdir -p %{buildroot}/usr/local/bin
DESTDIR=%{buildroot} cmake --install build --prefix=%{_prefix} || true
test -f %{buildroot}%{_prefix}/bin/flm || { echo "ERROR: flm binary not installed"; exit 1; }

# Remove files not needed at runtime
rm -rf %{buildroot}%{_prefix}/include
rm -rf %{buildroot}%{_prefix}/lib64

# Remove cmake-generated symlink in /usr/local/bin (wrong path for packaging)
rm -f %{buildroot}/usr/local/bin/flm 2>/dev/null || true

# Create correct symlink in /usr/bin/
# NOTE: _bindir is overridden to /opt/fastflowlm/bin by _prefix, so use /usr/bin explicitly
install -d %{buildroot}/usr/bin
ln -sf %{_prefix}/bin/flm %{buildroot}/usr/bin/flm

# Install flm-fetch-kernels helper script
install -Dm755 %{SOURCE1} %{buildroot}/usr/bin/flm-fetch-kernels

# VERSION file: read by flm-fetch-kernels to know which release to download
echo "%{version}" > %{buildroot}%{_prefix}/VERSION

%post
echo ""
echo "FastFlowLM installed."
echo ""
echo "To run NPU models, download the proprietary kernel binaries:"
echo ""
echo "  sudo flm-fetch-kernels"
echo ""
echo "Requires internet access to github.com/FastFlowLM/FastFlowLM"
echo ""
echo "Other requirements:"
echo "  - xdna-driver package (installs amdxdna kernel module via DKMS)"
echo "  - NPU firmware >= 1.1.0.0"
echo "  - unlimited memlock in /etc/security/limits.conf"
echo ""

%files
%license LICENSE_RUNTIME.txt
%doc README.md
%dir %{_prefix}
%dir %{_prefix}/bin
%{_prefix}/bin/flm
%{_prefix}/VERSION
%dir %{_prefix}/lib
%{_prefix}/lib/*.so
%dir %{_prefix}/share
%dir %{_prefix}/share/flm
%{_prefix}/share/flm/model_list.json
%{_prefix}/share/flm/xclbins/
/usr/bin/flm
/usr/bin/flm-fetch-kernels

%changelog
* Thu Apr 16 2026 Alessandro Lattao <alessandro@lattao.com> - 0.9.39-1
- Update to 0.9.39 (includes Gemma 4 model support)

* Sat Apr 11 2026 Alessandro Lattao <alessandro@lattao.com> - 0.9.38-1
- Initial Fedora packaging (source-only, MIT runtime)
- Proprietary NPU kernel binaries downloadable via flm-fetch-kernels
