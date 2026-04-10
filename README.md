# NV-Kernels GitHub Actions

This branch contains GitHub Actions workflows for the NV-Kernels repository.

## Workflows

### update-and-rebase.yml

Automatically rebases NVIDIA kernel branches onto the latest upstream stable tags from Greg KH's linux.git. Runs daily at midnight UTC and can be triggered manually.

**Supported branches:**
- `linux-nvidia-6.6`
- `linux-nvidia-6.12`
- `linux-nvidia-6.18`

When successful, creates rebased branches named `linux-nvidia-X.Y-vX.Y.Z` (e.g., `linux-nvidia-6.12-v6.12.65`).

### patchscan.yml

Checks that cherry-picked commits in a PR are not missing any upstream `Fixes:` patches. Runs on every PR targeting `24.04_linux-nvidia-6.17-next` and posts a comment listing any missing fixes, failing the check if any are found.

Uses `origin/linux` as the upstream reference. The patchscan script and its dependencies are stored in `.github/scripts/` so no changes are needed on target branches.

**Triggers:**
- Automatically on pull requests targeting `24.04_linux-nvidia-6.17-next`
- Manual dispatch (enter a PR number to scan)

### kernel-build.yml

Builds and tests kernels with the following matrix:

| Architecture | Config |
|-------------|--------|
| x86_64 | defconfig |
| ARM64 | 4K page size |
| ARM64 | 64K page size |

Includes boot tests via QEMU and runs kselftests for mm, dma, iommu, and locking subsystems.

**Triggers:**
- Manual dispatch (select branch to build)
- Automatically after successful rebase

## Branch Structure

- `linux` - Unmodified upstream Linux kernel mirror
- `github-actions` - This branch (GitHub Actions workflows only)
- `linux-nvidia-*` - NVIDIA kernel branches with patches on top of stable releases

## Why a separate `github-actions` branch?

The `linux` branch is an unmodified mirror of Torvalds' upstream kernel, kept in sync via a daily cron job that runs `git reset --hard` to match upstream. Any commits added to `linux` (including workflow files) would be wiped out on the next sync.

We needed a place to store the workflow files that wouldn't be affected by the upstream sync. Creating an orphan `github-actions` branch with only the `.github/workflows/` directory and a README solves this - it's completely independent of the kernel source tree.

## Why is this the default branch?

GitHub Actions scheduled workflows (`cron`) only run on the repository's **default branch**. Since our workflows live on `github-actions` and we wanted the daily rebase to run automatically, we set `github-actions` as the default branch.

This also keeps `linux` as a pristine upstream mirror with no extra commits on top.
