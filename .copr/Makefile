srpm:
	@PKG=$$(basename $$(dirname "$(spec)")); \
	VER=$$(grep '^Version:' "$(spec)" | awk '{print $$2}'); \
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
	dnf install -y git python3 rpm-build; \
	rm -rf $$PKG-$$VER $$PKG-$$VER.tar.gz; \
	echo "--- Cloning $$REPO @ $$BRANCH ---"; \
	git clone --recurse-submodules --branch $$BRANCH --depth 1 $$REPO $$PKG-$$VER; \
	if [ "$$PKG" = "xdna-driver" ]; then \
	    echo "--- Downloading NPU firmware ---"; \
	    cd $$PKG-$$VER; \
	    python3 -c " \
import json, urllib.request, os, sys; \
info = json.load(open('tools/info.json')); \
[( \
    os.makedirs('firmware/amdnpu/{}_{}'.format(fw['pci_device_id'], fw['pci_revision_id']), exist_ok=True), \
    print('  {} -> firmware/amdnpu/{}_{}/{}'.format(fw['fw_name'], fw['pci_device_id'], fw['pci_revision_id'], fw['fw_name'])), \
    urllib.request.urlretrieve(fw['url'], 'firmware/amdnpu/{}_{}/{}'.format(fw['pci_device_id'], fw['pci_revision_id'], fw['fw_name'])) \
) for fw in info['firmwares']]; \
sys.stdout.flush() \
"; \
	    cd ..; \
	fi; \
	tar czf $$PKG-$$VER.tar.gz $$PKG-$$VER; \
	find "$$(dirname "$(spec)")" -maxdepth 1 -type f ! -name "*.spec" -exec cp {} . \; ; \
	rpmbuild -bs \
	    --define "_sourcedir $$(pwd)" \
	    --define "_srcrpmdir $(outdir)" \
	    "$(spec)"; \
	rm -rf $$PKG-$$VER $$PKG-$$VER.tar.gz
