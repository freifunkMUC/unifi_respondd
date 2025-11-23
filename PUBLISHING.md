# Publishing Guide

This document describes how to publish a new release of `unifi_respondd` to PyPI.

## Prerequisites

1. **Configure Trusted Publishing on PyPI** (one-time setup):
   - Go to https://pypi.org/manage/project/unifi-respondd/settings/publishing/
   - Log in as an owner of the package
   - Add a new Trusted Publisher with the following settings:
     - Provider: GitHub
     - Owner: freifunkMUC
     - Repository name: unifi_respondd
     - Workflow filename: publish.yaml
     - Environment name: (leave empty)

2. **Configure Trusted Publishing on TestPyPI** (optional, for testing):
   - Go to https://test.pypi.org/manage/project/unifi-respondd/settings/publishing/
   - Follow the same steps as above

## Publishing a New Release

1. **Ensure all changes are merged to the main branch**
   - All code changes should be reviewed and merged
   - CI checks should pass

2. **Create and push a version tag**:
   ```bash
   # For a new release version (e.g., 0.0.9)
   git tag v0.0.9
   git push origin v0.0.9
   
   # For a major version (e.g., 1.0.0)
   git tag v1.0.0
   git push origin v1.0.0
   ```

3. **Wait for GitHub Actions to complete**:
   - The publish workflow will automatically build and publish to TestPyPI
   - If a tag was pushed, it will also publish to PyPI
   - Check the Actions tab: https://github.com/freifunkMUC/unifi_respondd/actions

4. **Verify the release**:
   - Check PyPI: https://pypi.org/project/unifi-respondd/
   - Test installation: `pip install unifi-respondd`

## Current Status

- ✅ Code has the fix for pyyaml Cython bug (`pyyaml==6.0.3`)
- ✅ Publish workflow is configured for Trusted Publishing
- ⚠️  PyPI project needs Trusted Publishing configuration (owner action required)
- ⏳ Waiting for new release to be tagged and published

## Troubleshooting

If publishing fails:
- Verify Trusted Publishing is configured correctly on PyPI
- Check that the workflow has `id-token: write` permission
- Ensure the tag starts with 'v' (e.g., v0.0.9, v1.0.0)
- Review the GitHub Actions logs for specific errors
