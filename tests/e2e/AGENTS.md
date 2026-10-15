## Build the Docker image for E2E testing

- Goal: Build the local image `crynux-node:e2e` using the e2e config template.

- Workflow:
  1. Ensure the current working directory is the repository root.
  2. Use target network `base` (`crynux-on-base-sepolia`).
  3. Copy `tests/e2e/config.yml.e2e_base` to `build/docker/config.yml.example`.
  4. Copy `src/webui/src/config.base.json` to `src/webui/src/config.json`.
  5. Build the image from `build/docker/Dockerfile` with tag `crynux-node:e2e`.
  6. Verify `crynux-node:e2e` exists locally.

- Contract addresses in `tests/e2e/config.yml.e2e_base` MUST match `crynux-contracts/deployments/primary/testnet/crynux-on-base-sepolia/contracts.json` `nodeContracts`.
- Preloaded models in that config MUST be `qwen/qwen-image-2.1` for `sd_base` and `qwen/qwen3-8b` for `gpt_base`.

## Prepare the mount folder for the Docker image

- Goal: Prepare node host-side files in a Docker mount workspace for local e2e network runs.

- Workspace rule:
  - Choose one mount workspace root directory and use it consistently in compose volume mappings.
  - Reuse existing files in that workspace when possible instead of recreating everything.

- Required node structure:

```text
<mount-root>/
  config/
```

## Prepare the node wallet account

- Goal: Prepare the node wallet private key file used by the node container.

- Required wallet file:

```text
<mount-root>/config/private_key.txt
```

- Wallet account requirements:
  - `NODE_PRIVATE_KEY` must be provided as a single-line private key value with `0x` prefix.
  - The key material must be persisted at `<mount-root>/config/private_key.txt` with no trailing whitespace.


## Top up the node wallet account

The balance of the node wallet account must be greater than `500 CNX` to cover the minimum staking amount and node join tx gas fee.
