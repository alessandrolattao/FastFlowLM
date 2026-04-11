# Publishing to COPR

Packages are published to COPR automatically when changes are pushed to `main`.
The COPR webhook triggers a new build for any push.

## One-time setup

### 1. Fedora account (FAS)

Register at https://accounts.fedoraproject.org/ if you don't have one.

### 2. Configure the API token

Get your token at https://copr.fedorainfracloud.org/api/ and save it to
`~/.config/copr`:

```ini
[copr-cli]
login = alessandrolattao
username = alessandrolattao
token = <your-token>
copr_url = https://copr.fedorainfracloud.org
```

### 3. GitHub secret for auto-updates

The `check-updates.yml` workflow needs write access to push version bumps:

| Secret | Value |
|---|---|
| `AUTO_UPDATE_TOKEN` | GitHub Personal Access Token with `contents: write` scope |

Create one at https://github.com/settings/tokens and add it under
`Settings > Secrets and variables > Actions`.

## Automatic version updates

`.github/workflows/check-updates.yml` runs daily at 07:00 UTC and:

1. Checks for new releases of `amd/xdna-driver` and `FastFlowLM/FastFlowLM`
2. Updates the spec files if a newer version is found
3. Pushes the commit, which triggers a COPR rebuild via webhook

No manual intervention needed when upstream releases a new version.

## Manual upload

```sh
# Build xdna-driver first (FastFlowLM depends on it)
make copr-xdna

# Wait for the COPR build to succeed, then:
make copr-flm
```

## COPR project

https://copr.fedorainfracloud.org/coprs/alessandrolattao/fastflowlm/
