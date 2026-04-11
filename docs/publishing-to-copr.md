# Publishing to COPR

Packages are published to COPR automatically via GitHub Actions when changes
are pushed to `main`. Manual upload is also supported.

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

### 3. Create the COPR project (first time only)

```sh
sudo dnf install copr-cli

copr-cli create fastflowlm \
    --chroot fedora-rawhide-x86_64 \
    --chroot fedora-43-x86_64 \
    --description "FastFlowLM - Run LLMs on AMD Ryzen AI NPUs" \
    --instructions "sudo dnf copr enable alessandrolattao/fastflowlm && sudo dnf install fastflowlm && sudo flm-fetch-kernels"
```

### 4. Add GitHub secrets

Add the following secrets to the GitHub repository
(`Settings > Secrets and variables > Actions`):

| Secret | Value |
|---|---|
| `COPR_LOGIN` | the `login` field from `~/.config/copr` |
| `COPR_TOKEN` | the `token` field from `~/.config/copr` |

## Automatic builds (GitHub Actions)

Two workflows handle SRPM submission to COPR:

- `.github/workflows/build-xdna-driver.yml` - triggers on changes to `xdna-driver/**` or `Makefile`
- `.github/workflows/build-fastflowlm.yml` - triggers on changes to `fastflowlm/**` or `Makefile`

On push to `main`, each workflow:
1. Generates the `.src.rpm` with `make srpm-xdna` / `make srpm-flm`
2. Submits it to COPR with `copr-cli build --nowait`
3. COPR compiles the RPM in a clean chroot

Build status is visible at:
https://copr.fedorainfracloud.org/coprs/alessandrolattao/fastflowlm/

## Manual upload

```sh
# Build xdna-driver first (fastflowlm depends on it)
make copr-xdna

# Wait for the COPR build to succeed, then:
make copr-flm
```

## Updating versions

### xdna-driver

1. Update `Version:` in `xdna-driver/xdna-driver.spec`
2. Update `%changelog`
3. `git commit && git push` - GitHub Actions submits the new SRPM to COPR

### fastflowlm

1. Update `Version:` in `fastflowlm/fastflowlm.spec`
2. Update `%changelog`
3. `git commit && git push` - GitHub Actions submits the new SRPM to COPR
