%global debug_package %{nil}
%global _prefix /opt/fastflowlm

# Minimum expected NPU driver version (passed to CMake)
%global npu_version 32.0.203.304

# The /opt/fastflowlm/bin/flm binary is linked against the proprietary NPU
# runtime libraries (libdequant.so, libgemm.so, lib*_npu.so, ...) which
# this RPM intentionally does NOT ship (they live under LICENSE_BINARY.txt
# v2.0 and are fetched at runtime by flm-fetch-kernels). Suppress the
# automatically generated DT_NEEDED -> Requires entries for those libs so
# dnf can install the package without trying to satisfy them.
%global __requires_exclude ^lib(dequant|gemm|gemma4e_npu|gemma_embedding|gemma_npu|gemma_text_npu|gpt_oss_npu|lfm2_npu|llama_npu|lm_head|mha|nanbeige_npu|phi4_npu|q4_npu_eXpress|qwen2_npu|qwen2vl_npu|qwen3_5vl_npu|qwen3_npu|qwen3vl_npu|whisper_npu)[.]so

Name:           fastflowlm
Version:        0.9.43
Release:        2%{?dist}
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
cd src
# cmake install(CODE) creates /usr/local/bin/flm outside DESTDIR (ignores env).
# Pre-create it inside buildroot so the symlink lands there; ignore any failure.
mkdir -p %{buildroot}/usr/local/bin
DESTDIR=%{buildroot} cmake --install build --prefix=%{_prefix} || true
test -f %{buildroot}%{_prefix}/bin/flm || { echo "ERROR: flm binary not installed"; exit 1; }

# Remove files not needed at runtime
rm -rf %{buildroot}%{_prefix}/include

# Strip out the proprietary NPU kernel binaries that upstream ships as
# prebuilt blobs (covered by LICENSE_BINARY.txt, NOT by the MIT License
# declared above). They are downloaded at first run by flm-fetch-kernels,
# which requires the user to explicitly accept the proprietary EULA.
#   - lib64/flm/*.so   : per-model NPU runtime libraries
#   - share/flm/xclbins/ : compiled NPU kernels
rm -rf %{buildroot}%{_prefix}/lib64/flm
rm -rf %{buildroot}%{_prefix}/share/flm/xclbins

# Keep the empty target directories so flm-fetch-kernels has a stable
# install location owned by this package.
install -d %{buildroot}%{_prefix}/lib64/flm
install -d %{buildroot}%{_prefix}/share/flm/xclbins

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
echo "Next step: download the proprietary NPU kernel binaries from the"
echo "official release (requires internet access to github.com):"
echo ""
echo "  sudo flm-fetch-kernels"
echo ""

%files
%license LICENSE_RUNTIME.txt
%doc README.md
%dir %{_prefix}
%dir %{_prefix}/bin
%{_prefix}/bin/flm
%{_prefix}/VERSION
# Empty directories owned by this package. The proprietary NPU runtime
# libraries (lib64/flm/*.so) and compiled NPU kernels (share/flm/xclbins/)
# are installed into these directories at first run by flm-fetch-kernels.
%dir %{_prefix}/lib64
%dir %{_prefix}/lib64/flm
%dir %{_prefix}/share
%dir %{_prefix}/share/flm
%dir %{_prefix}/share/flm/xclbins
%{_prefix}/share/flm/model_list.json
/usr/bin/flm
/usr/bin/flm-fetch-kernels

%changelog
* Mon Jun 08 2026 Alessandro Lattao <alessandro@lattao.com> - 0.9.43-2
- Drop the '%%global __os_install_post %%{nil}' override (keep only
  debug_package %%{nil}) so the flm binary ships stripped.
- flm-fetch-kernels: use 'curl -fL' so a failed download (e.g. a 404) aborts
  with a clear error instead of saving an HTML error page as the .deb.
- flm-fetch-kernels: accept 'yes' (not just 'y') at the confirmation prompts.

* Wed May 27 2026 Alessandro Lattao <alessandro@lattao.com> - 0.9.43-1
- Update to 0.9.43

* Wed May 20 2026 Alessandro Lattao <alessandro@lattao.com> - 0.9.42-5
- Fix unsatisfiable Requires introduced in -4: /opt/fastflowlm/bin/flm
  has DT_NEEDED entries for the 19 proprietary NPU runtime libraries
  that this RPM no longer ships, and rpmbuild's automatic dependency
  generator turned each entry into a Requires (libdequant.so()(64bit)
  &c.), making the package uninstallable. Filter those entries out via
  %%__requires_exclude. The .so files are still fetched at first run
  by flm-fetch-kernels.

* Wed May 20 2026 Alessandro Lattao <alessandro@lattao.com> - 0.9.42-4
- Honor the MIT license declaration of this package: strip the prebuilt
  NPU kernel binaries (lib64/flm/*.so and share/flm/xclbins/) from the
  RPM payload at %%install time. Those blobs are covered by upstream's
  LICENSE_BINARY.txt v2.0 (proprietary) and must not ship in a package
  whose %%license is MIT.
- The empty lib64/flm/ and share/flm/xclbins/ directories are still
  owned by this package so that flm-fetch-kernels has a stable, package-
  managed install location.
- flm-fetch-kernels: fix install paths to match upstream 0.9.42 layout:
  blobs are extracted from opt/fastflowlm/lib/flm/ in the .deb (subdir
  added by upstream) and installed into /opt/fastflowlm/lib64/flm/ on
  Fedora (CMAKE_INSTALL_LIBDIR=lib64), matching the rpath the binary
  was linked with.

* Wed May 20 2026 Alessandro Lattao <alessandro@lattao.com> - 0.9.42-3
- %%post: drop stale references to DKMS and to manual memlock setup
  (memlock is now configured by xdna-driver) and reduce the message
  to the only action the user still needs to take: running
  flm-fetch-kernels to download the proprietary NPU kernel binaries

* Wed May 20 2026 Alessandro Lattao <alessandro@lattao.com> - 0.9.42-2
- Fix install paths: upstream moved .so libraries from lib/ to lib64/flm/

* Thu May 14 2026 Alessandro Lattao <alessandro@lattao.com> - 0.9.42-1
- Update to 0.9.42

* Thu May 7 2026 Alessandro Lattao <alessandro@lattao.com> - 0.9.41-1
- Update to 0.9.41

* Wed Apr 29 2026 Alessandro Lattao <alessandro@lattao.com> - 0.9.40-1
- Update to 0.9.40

* Thu Apr 16 2026 Alessandro Lattao <alessandro@lattao.com> - 0.9.39-1
- Update to 0.9.39 (includes Gemma 4 model support)

* Sat Apr 11 2026 Alessandro Lattao <alessandro@lattao.com> - 0.9.38-1
- Initial Fedora packaging (source-only, MIT runtime)
- Proprietary NPU kernel binaries downloadable via flm-fetch-kernels
