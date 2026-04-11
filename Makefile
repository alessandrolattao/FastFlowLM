COPR_USER   = alessandrolattao
COPR_REPO   = fastflowlm
OUTDIR      = $(shell pwd)/out

.PHONY: all srpm-xdna srpm-flm copr-xdna copr-flm copr \
        bump-xdna bump-flm clean help

help:
	@echo "Available targets:"
	@echo "  srpm-xdna        Generate SRPM for xdna-driver"
	@echo "  srpm-flm         Generate SRPM for fastflowlm"
	@echo "  copr-xdna        Submit xdna-driver to COPR (waits for completion)"
	@echo "  copr-flm         Submit fastflowlm to COPR"
	@echo "  copr             Submit both to COPR in order (xdna first)"
	@echo "  bump-xdna VER=x  Bump xdna-driver version in spec"
	@echo "  bump-flm  VER=x  Bump fastflowlm version in spec"
	@echo "  clean            Remove build artifacts"
	@echo ""
	@echo "Local source caching (skips network clone):"
	@echo "  sources/xdna-driver   -> github.com/amd/xdna-driver"
	@echo "  sources/fastflowlm    -> github.com/FastFlowLM/FastFlowLM"

# --- SRPM helpers ---

# build-srpm: generate a .src.rpm from a spec file
# Usage: $(call build-srpm,<spec-path>)
define build-srpm
	dnf install -y git python3 ; \
	SPEC="$(1)"; \
	PKG=$$(basename $$(dirname "$$SPEC")); \
	VER=$$(grep '^Version:' "$$SPEC" | awk '{print $$2}'); \
	echo "--- Building SRPM: $$PKG v$$VER ---"; \
	if [ "$$PKG" = "xdna-driver" ]; then \
	    REPO="https://github.com/amd/xdna-driver"; \
	    BRANCH="$$VER"; \
	elif [ "$$PKG" = "fastflowlm" ]; then \
	    REPO="https://github.com/FastFlowLM/FastFlowLM"; \
	    BRANCH="v$$VER"; \
	else \
	    echo "Unknown package: $$PKG"; exit 1; \
	fi; \
	rm -rf $$PKG-$$VER $$PKG-$$VER.tar.gz; \
	LOCAL_SRC="$$(dirname "$$SPEC")/../sources/$$PKG"; \
	if [ -d "$$LOCAL_SRC" ]; then \
	    echo "--- Using local source: $$LOCAL_SRC ---"; \
	    cp -a "$$LOCAL_SRC" "$$PKG-$$VER"; \
	else \
	    echo "--- Cloning $$REPO @ $$BRANCH ---"; \
	    git clone --recurse-submodules --branch $$BRANCH --depth 1 $$REPO $$PKG-$$VER; \
	fi; \
	if [ "$$PKG" = "xdna-driver" ]; then \
	    echo "--- Downloading NPU firmware ---"; \
	    cd $$PKG-$$VER; \
	    python3 -c " \
import json, urllib.request, os, sys; \
info = json.load(open('tools/info.json')); \
[( \
    os.makedirs('firmware/amdnpu/{}_{}'.format(fw['pci_device_id'], fw['pci_revision_id']), exist_ok=True), \
    print('  {} {} -> firmware/amdnpu/{}_{}/{}'.format(fw['device'], fw['version'], fw['pci_device_id'], fw['pci_revision_id'], fw['fw_name'])), \
    urllib.request.urlretrieve(fw['url'], 'firmware/amdnpu/{}_{}/{}'.format(fw['pci_device_id'], fw['pci_revision_id'], fw['fw_name'])) \
) for fw in info['firmwares']]; \
sys.stdout.flush() \
"; \
	    cd ..; \
	fi; \
	tar czf $$PKG-$$VER.tar.gz $$PKG-$$VER; \
	find "$$(dirname "$$SPEC")" -maxdepth 1 -type f ! -name "*.spec" \
	    -exec cp {} $$(pwd)/ \; ; \
	rpmbuild -bs \
	    --define "_sourcedir $$(pwd)" \
	    --define "_srcrpmdir $(OUTDIR)" \
	    "$$SPEC"; \
	rm -rf $$PKG-$$VER $$PKG-$$VER.tar.gz
endef

# --- SRPM ---

srpm-xdna:
	@mkdir -p $(OUTDIR)
	$(call build-srpm,$(shell pwd)/xdna-driver/xdna-driver.spec)

srpm-flm:
	@mkdir -p $(OUTDIR)
	$(call build-srpm,$(shell pwd)/fastflowlm/fastflowlm.spec)

# --- COPR upload ---

copr-xdna: srpm-xdna
	copr-cli build $(COPR_USER)/$(COPR_REPO) $(OUTDIR)/xdna-driver-*.src.rpm

copr-flm: srpm-flm
	copr-cli build $(COPR_USER)/$(COPR_REPO) $(OUTDIR)/fastflowlm-*.src.rpm --nowait

copr: srpm-xdna srpm-flm
	copr-cli build $(COPR_USER)/$(COPR_REPO) $(OUTDIR)/xdna-driver-*.src.rpm
	copr-cli build $(COPR_USER)/$(COPR_REPO) $(OUTDIR)/fastflowlm-*.src.rpm --nowait

# --- Version bump ---

bump-xdna:
	@[ -n "$(VER)" ] || { echo "Usage: make bump-xdna VER=2.21.76"; exit 1; }
	@SPEC=xdna-driver/xdna-driver.spec; \
	DATE=$$(date '+%a %b %-d %Y'); \
	sed -i "s/^Version:.*/Version:        $(VER)/" $$SPEC; \
	sed -i "s/^Release:.*/Release:        1%{?dist}/" $$SPEC; \
	awk -v new_ver="$(VER)" -v date="$$DATE" ' \
	  /^%changelog/ { \
	    print; \
	    print "* " date " Alessandro Lattao <alessandro@lattao.com> - " new_ver "-1"; \
	    print "- Update to " new_ver; \
	    print ""; \
	    next \
	  } 1' $$SPEC > $$SPEC.tmp && mv $$SPEC.tmp $$SPEC; \
	echo "Bumped xdna-driver to $(VER)"

bump-flm:
	@[ -n "$(VER)" ] || { echo "Usage: make bump-flm VER=0.9.39"; exit 1; }
	@SPEC=fastflowlm/fastflowlm.spec; \
	DATE=$$(date '+%a %b %-d %Y'); \
	sed -i "s/^Version:.*/Version:        $(VER)/" $$SPEC; \
	sed -i "s/^Release:.*/Release:        1%{?dist}/" $$SPEC; \
	awk -v new_ver="$(VER)" -v date="$$DATE" ' \
	  /^%changelog/ { \
	    print; \
	    print "* " date " Alessandro Lattao <alessandro@lattao.com> - " new_ver "-1"; \
	    print "- Update to " new_ver; \
	    print ""; \
	    next \
	  } 1' $$SPEC > $$SPEC.tmp && mv $$SPEC.tmp $$SPEC; \
	echo "Bumped fastflowlm to $(VER)"

# --- Clean ---

clean:
	rm -rf $(OUTDIR)
