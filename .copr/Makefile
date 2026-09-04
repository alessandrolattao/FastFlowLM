# COPR "make_srpm" entry point: COPR clones this repo and calls this target to
# produce the SRPM it then builds in every chroot.
#
# xdna-driver only: the NPU firmware is not in the git tree, it is fetched here
# and packed into the tarball. Upstream's 1.9 branch dropped the "firmwares"
# array from tools/info.json in favour of a WHENCE manifest (tools/WHENCE,
# pinned to an immutable drm-firmware commit) consumed by their own
# tools/sync_from_whence.py, so call that script rather than parsing the
# manifest here -- the schema stays upstream's problem. The failure is fatal on
# purpose: the inline parser it replaces was joined to the rest of the recipe
# with ';', so when info.json changed shape it died with a KeyError, the SRPM
# was still built (without a single firmware file) and every chroot then failed
# much later at %files with a missing /usr/lib/firmware/amdnpu.
srpm:
	@PKG=$$(basename $$(dirname "$(spec)")); \
	VER=$$(grep '^Version:' "$(spec)" | awk '{print $$2}'); \
	echo "--- Building SRPM: $$PKG v$$VER ---"; \
	if [ "$$PKG" = "xdna-driver" ]; then \
	    REPO="https://github.com/amd/xdna-driver"; \
	    BRANCH=$$(awk '/^%global amd_branch/{print $$3}' "$(spec)"); \
	    AMD_COMMIT=$$(awk '/^%global amd_commit/{print $$3}' "$(spec)"); \
	elif [ "$$PKG" = "fastflowlm" ]; then \
	    REPO="https://github.com/FastFlowLM/FastFlowLM"; \
	    BRANCH="v$$VER"; \
	else \
	    echo "Unknown package: $$PKG"; exit 1; \
	fi; \
	dnf install -y git python3 rpm-build; \
	rm -rf $$PKG-$$VER $$PKG-$$VER.tar.gz; \
	echo "--- Cloning $$REPO @ $$BRANCH ---"; \
	if [ -n "$$AMD_COMMIT" ]; then \
	    git clone --recurse-submodules --branch $$BRANCH $$REPO $$PKG-$$VER; \
	    git -C $$PKG-$$VER checkout "$$AMD_COMMIT"; \
	    git -C $$PKG-$$VER submodule update --init --recursive; \
	else \
	    git clone --recurse-submodules --branch $$BRANCH --depth 1 $$REPO $$PKG-$$VER; \
	fi; \
	if [ "$$PKG" = "xdna-driver" ]; then \
	    echo "--- Downloading NPU firmware ---"; \
	    ( cd $$PKG-$$VER && \
	      python3 tools/sync_from_whence.py firmware \
	          --whence tools/WHENCE --out firmware/amdnpu ) || exit 1; \
	fi; \
	tar czf $$PKG-$$VER.tar.gz $$PKG-$$VER; \
	find "$$(dirname "$(spec)")" -maxdepth 1 -type f ! -name "*.spec" -exec cp {} . \; ; \
	rpmbuild -bs \
	    --define "_sourcedir $$(pwd)" \
	    --define "_srcrpmdir $(outdir)" \
	    "$(spec)"; \
	rm -rf $$PKG-$$VER $$PKG-$$VER.tar.gz
