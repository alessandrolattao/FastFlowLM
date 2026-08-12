%global debug_package %{nil}
%global _prefix /opt/fastflowlm

# Minimum expected NPU driver version (passed to CMake)
%global npu_version 32.0.203.304

# NPU runtime backend. Upstream keeps the prebuilt engine blobs in
# src/lib/<backend>/ and builds against XRT unless FLM_USE_HRX=ON; we use the
# XRT one, since HRX would mean shipping upstream's bundled libhrx too.
%global flm_backend xrt

# The /opt/fastflowlm/bin/flm binary is linked against the proprietary NPU
# runtime libraries (libdequant.so, libgemm.so, lib*_npu.so, ...) which
# this RPM intentionally does NOT ship (they live under LICENSE_BINARY.txt
# v2.0 and are fetched at runtime by flm-fetch-kernels). Suppress the
# automatically generated DT_NEEDED -> Requires entries for those libs so
# dnf can install the package without trying to satisfy them.
#
# Matched by shape, not by an explicit roster: every new model upstream adds
# ships another lib<model>_npu.so, and an exhaustive list silently produces an
# uninstallable package the first time one is missing (v1.0.0 added
# libqwen3_5_omni_npu.so and the resulting RPM could not be installed at all,
# because nothing provides that soname). The remaining alternatives are the
# handful of engine libs that do not carry the _npu suffix.
#
# The authoritative roster is the source tree itself: upstream ships the blobs
# under src/lib/<backend>/ (src/lib/xrt for this build) and CMake picks them up
# with file(GLOB). It cannot be turned into this macro directly -- the macro is
# needed before %%prep unpacks that directory -- so %%install cross-checks the
# two and fails the build if this pattern ever stops covering them.
%global __requires_exclude ^lib([[:alnum:]_]+_npu|dequant[[:alnum:]_]*|gemm|gemma_embedding|lm_head|mha|q4_npu_eXpress)[.]so

Name:           fastflowlm
Version:        1.0.1
Release:        4%{?dist}
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
# CMAKE_INSTALL_LIBDIR must be pinned explicitly. Upstream defaults it to "lib"
# (src/CMakeLists.txt), but only via `if(NOT CMAKE_INSTALL_LIBDIR)` -- and
# third_party/tokenizers-cpp/sentencepiece runs include(GNUInstallDirs) from an
# add_subdirectory() earlier in the file, which populates that variable in the
# CMake *cache*. On Fedora GNUInstallDirs resolves to lib64, so the upstream
# default never applies and the install layout silently flips between releases
# depending on subdirectory ordering (lib64/flm -> lib -> lib64 so far).
# Passing it on the command line pre-populates the cache entry, which
# GNUInstallDirs then leaves alone: the layout stays "lib" on every distro,
# identical to what upstream's own debian/rules produces.
cmake --preset linux-default \
    -DXRT_INCLUDE_DIR=/opt/xilinx/xrt/include \
    -DXRT_LIB_DIR=/opt/xilinx/xrt/lib \
    -DCMAKE_INSTALL_LIBDIR=lib \
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
#   - lib/*.so         : per-model NPU runtime libraries (flat lib/, pinned
#                        via CMAKE_INSTALL_LIBDIR in %%build)
#   - share/flm/xclbins/ : compiled NPU kernels
removed_libs=$(ls %{buildroot}%{_prefix}/lib/lib*.so 2>/dev/null | xargs -r -n1 basename)
rm -f %{buildroot}%{_prefix}/lib/lib*.so
rm -rf %{buildroot}%{_prefix}/share/flm/xclbins

# Safety net for the removal above. The install layout is pinned, but if a
# future upstream release moves the blobs somewhere we do not expect, fail the
# build loudly rather than silently shipping proprietary binaries inside a
# package declared MIT.
leftover=$(find %{buildroot}%{_prefix} \( -name '*.so' -o -name '*.so.*' \) | sort)
if [ -n "$leftover" ]; then
    echo "ERROR: unexpected shared objects left in buildroot:"
    echo "$leftover"
    echo "These are most likely upstream's proprietary NPU blobs under a new"
    echo "path. Update the removal above before packaging this release."
    exit 1
fi

# Second safety net, for the Requires filter rather than the payload.
# __requires_exclude matches the engine libraries by shape, which covers every
# lib<model>_npu.so upstream has added so far but cannot cover a name in a shape
# nobody has used yet. Left alone, that failure mode is invisible here: the
# build succeeds and produces a package that simply refuses to install, because
# rpm generated a Requires on a soname nothing provides. So cross-check every
# DT_NEEDED entry pointing at a library we just deleted, and fail the build with
# the name to add if the filter does not already cover it.
uncovered=""
for soname in $(readelf -d %{buildroot}%{_prefix}/bin/flm | awk -F'[][]' '/NEEDED/{print $2}'); do
    # removed_libs is newline-separated, so match whole lines rather than
    # padding it with spaces: a space-delimited test never fires here.
    printf '%s\n' "$removed_libs" | grep -qxF "$soname" || continue
    printf '%s' "$soname" | grep -qE '%{__requires_exclude}' || uncovered="$uncovered $soname"
done
if [ -n "$uncovered" ]; then
    echo "ERROR: flm links against removed NPU libraries that __requires_exclude"
    echo "does not match:$uncovered"
    echo "rpm would emit an unsatisfiable Requires for each of them and the"
    echo "resulting package would build fine but fail to install. Widen"
    echo "%%__requires_exclude at the top of this spec to cover them."
    echo "The full set upstream ships lives in src/lib/%{flm_backend}/."
    exit 1
fi

# Keep the empty target directories so flm-fetch-kernels has a stable
# install location owned by this package.
install -d %{buildroot}%{_prefix}/lib
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
# libraries (lib/*.so) and compiled NPU kernels (share/flm/xclbins/)
# are installed into these directories at first run by flm-fetch-kernels.
%dir %{_prefix}/lib
%dir %{_prefix}/share
%dir %{_prefix}/share/flm
%dir %{_prefix}/share/flm/xclbins
# Glob rather than an explicit list: upstream adds metadata files here between
# releases (model_info.json arrived in v0.9.46) and an exact filename turns
# every such addition into a build failure.
%{_prefix}/share/flm/*.json
/usr/bin/flm
/usr/bin/flm-fetch-kernels

%changelog
* Wed Aug 12 2026 Alessandro Lattao <alessandro@lattao.com> - 1.0.1-4
- Fix the Requires cross-check added in 1.0.1-3, which never ran. It tested
  membership with `case " $removed_libs " in *" $soname "*`, but removed_libs
  comes from xargs and is newline-separated, so no entry was ever surrounded by
  the spaces the pattern expects and every soname was skipped. Match whole
  lines instead. The package payload is unchanged.

* Wed Aug 12 2026 Alessandro Lattao <alessandro@lattao.com> - 1.0.1-3
- Match the NPU engine libraries in __requires_exclude by shape instead of
  listing them one by one. v1.0.0 added libqwen3_5_omni_npu.so, which was
  missing from the roster, so 1.0.1-2 built successfully but could not be
  installed: nothing provides that soname and dnf had no way to satisfy the
  generated Requires.

* Wed Aug 12 2026 Alessandro Lattao <alessandro@lattao.com> - 1.0.1-2
- Fix packaging failure that has blocked every build since v0.9.46. Two
  independent causes, both fixed so they cannot recur:
  - Pin CMAKE_INSTALL_LIBDIR=lib at configure time. Upstream's "lib" default
    is guarded by if(NOT CMAKE_INSTALL_LIBDIR), but sentencepiece (pulled in
    via third_party/tokenizers-cpp) runs include(GNUInstallDirs) first and
    caches lib64 on Fedora, so the layout flipped to lib64/ in v1.0.0 and the
    NPU blobs escaped the %%install removal. Upstream never sees this because
    debian/rules only ever builds on Debian, where GNUInstallDirs picks lib.
  - Own share/flm/*.json by glob instead of naming model_list.json. Upstream
    added model_info.json in v0.9.46, which alone broke that build.
- Add a buildroot guard that fails the build if any .so survives the blob
  removal, so a future layout change cannot silently ship proprietary NPU
  binaries in an MIT-declared package.

* Wed Aug 12 2026 Alessandro Lattao <alessandro@lattao.com> - 1.0.1-1
- Update to 1.0.1

* Tue Aug 11 2026 Alessandro Lattao <alessandro@lattao.com> - 1.0.0-1
- Update to 1.0.0

* Wed Jul 29 2026 Alessandro Lattao <alessandro@lattao.com> - 0.9.46-1
- Update to 0.9.46

* Sat Jul 11 2026 Eerik Saarinen <eerik.saarinen@gmail.com> - 0.9.45-2
- Fix packaging failure: upstream v0.9.44+ dropped lib64/flm/ in favour of
  a flat lib/ dir (RUNPATH $ORIGIN/../lib); update %%install to strip
  lib/*.so instead of lib64/flm/ and %%files to own lib/ instead of
  lib64/ + lib64/flm/
- flm-fetch-kernels: update LIB_DEST to lib/ and DEB_LIB to lib/ to
  match the new .deb layout (lib/*.so, no flm/ subdir)
- Add libdequant_new and libqwen3_6_moe_npu to %%__requires_exclude
  (new libs introduced in v0.9.45)

* Sat Jul 11 2026 Alessandro Lattao <alessandro@lattao.com> - 0.9.45-1
- Update to 0.9.45

* Mon Jul 6 2026 Alessandro Lattao <alessandro@lattao.com> - 0.9.44-1
- Update to 0.9.44

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
