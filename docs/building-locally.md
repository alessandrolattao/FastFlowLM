# Building Locally

Build and test the SRPMs on a Fedora machine without uploading to COPR.

## Prerequisites

```sh
sudo dnf install git python3 rpm-build rpmdevtools copr-cli
```

## Build xdna-driver SRPM

```sh
cd ~/Projects/alessandrolattao/fastflowlm
make srpm-xdna
```

The SRPM will be in `out/`.

## Build fastflowlm SRPM

```sh
make srpm-flm
```

The SRPM will be in `out/`.

## Submit manually to COPR

```sh
# Build xdna-driver first (fastflowlm depends on it)
make copr-xdna

# Wait for the COPR build to succeed, then:
make copr-flm
```

## Notes

- If `sources/xdna-driver` or `sources/fastflowlm` exist locally, the build uses
  those instead of cloning from GitHub. Delete them to force a fresh clone.
- The xdna-driver build downloads NPU firmware from the URLs in `tools/info.json`
  at build time.
