# NV-Kernels GitHub Actions

This branch contains GitHub Actions workflows for the NV-Kernels repository.

## Workflows

### update-and-rebase.yml
Runs daily at midnight UTC (and on-demand). Rebases NVIDIA patch branches onto the latest upstream stable tags:
- `linux-nvidia-6.6`
- `linux-nvidia-6.12`
- `linux-nvidia-6.18`

### kernel-build.yml
Runs on push and pull requests. Builds and tests the kernel:
- x86_64 with defconfig
- ARM64 with 4K page size config
- ARM64 with 64K page size config

Includes boot tests and kselftests for mm, dma, iommu, and locking subsystems.

## Branch Structure

- `linux` - Unmodified upstream Linux kernel mirror
- `github-actions` - This branch (GitHub Actions workflows only)
- `linux-nvidia-*` - NVIDIA kernel branches with patches on top of stable releases
