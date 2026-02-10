# avionmqtt

Bridge Avion Bluetooth mesh lights to MQTT/Home Assistant.

## Release Process

Releases are fully automated via GitHub Actions. Pushing a version tag triggers:

1. Build wheel and source tarball
2. Publish to PyPI (trusted publishing)
3. Create GitHub release with attached artifacts

### Steps

1. Bump version in `pyproject.toml`
2. Commit: `git commit -am "Bump to v0.X.0"`
3. Tag and push: `git tag v0.X.0 && git push && git push --tags`

The workflow `.github/workflows/workflow.yml` runs on `push: tags: ['v*']`.

## Architecture

- Uses `avionmesh` for BLE mesh communication (CSRMesh protocol)
- Uses `avionhttp` for Avi-on cloud API (device discovery)
- MQTT bridge for Home Assistant integration
- Independent MQTT and mesh operation

## Code Style

- Ruff for linting/formatting (`ruff check --fix src/`)
- mypy for type checking (`mypy src/`)
