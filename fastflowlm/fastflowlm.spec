%global debug_package %{nil}
%global __os_install_post %{nil}
%global _prefix /opt/fastflowlm

# Minimum expected NPU driver version (passed to CMake)
%global npu_version 32.0.203.304

Name:           fastflowlm
Version:        0.9.38
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
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  pkgconfig
BuildRequires:  git
BuildRequires:  ffmpeg-free-devel
BuildRequires:  boost-devel
BuildRequires:  libcurl-devel
BuildRequires:  libdrm-devel
BuildRequires:  fftw-devel
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
# Install into buildroot
cd src
DESTDIR=%{buildroot} cmake --install build --prefix=%{_prefix}

# Remove include dir (not needed at runtime)
rm -rf %{buildroot}%{_prefix}/include

# Remove CMake-generated /usr/local/bin/flm symlink (points outside buildroot)
rm -f %{buildroot}/usr/local/bin/flm 2>/dev/null || true

# Create correct symlink in /usr/bin/
install -d %{buildroot}%{_bindir}
ln -sf %{_prefix}/bin/flm %{buildroot}%{_bindir}/flm

# Install flm-fetch-kernels helper script
install -Dm755 %{SOURCE1} %{buildroot}%{_bindir}/flm-fetch-kernels

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
%{_prefix}/bin/flm
%{_prefix}/VERSION
%{_prefix}/share/flm/model_list.json
%dir %{_prefix}/lib
%dir %{_prefix}/share/flm
%{_bindir}/flm
%{_bindir}/flm-fetch-kernels

%changelog
* Sat Apr 11 2026 Alessandro Lattao <alessandro@lattao.com> - 0.9.38-1
- Initial Fedora packaging (source-only, MIT runtime)
- Proprietary NPU kernel binaries downloadable via flm-fetch-kernels
