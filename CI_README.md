# CI Pipeline Guide

## GitHub Actions Continuous Integration

This repository includes a comprehensive CI pipeline that runs on every push and pull request to `main` and `develop` branches.

### Pipeline Steps

The CI pipeline runs the following checks on both **Ubuntu** and **Windows** runners:

1. **Checkout**: Downloads the repository code
2. **Setup Python 3.11**: Installs the specified Python version
3. **Cache Dependencies**: Speeds up builds by caching pip packages
4. **Install Dependencies**: Installs packages from `requirements.txt`
5. **Linting Check**: Runs `ruff check .` to find code issues
6. **Format Check**: Runs `ruff format --check .` to ensure code formatting
7. **Unit Tests**: Runs `pytest` to execute test suite
8. **Docker Build**: Verifies the Docker image builds successfully (Ubuntu only)

### Before Committing

To ensure your code passes the CI pipeline:

```bash
cd continuum-node

# Install dependencies (if not already done)
pip install -r requirements.txt

# Fix linting issues
ruff check . --fix

# Format your code (REQUIRED)
ruff format .

# Run tests locally
pytest

# Test Docker build (optional)
docker build . -t continuum:test
```

### Important Notes

- **Formatting is mandatory**: The pipeline will **fail** if code is not properly formatted with ruff
- **All tests must pass**: Both unit tests and linting checks must succeed
- **Cross-platform compatibility**: Code must work on both Ubuntu and Windows
- **Docker validation**: The Dockerfile must build successfully

### Local Development Commands

```bash
# Format code
ruff format .

# Check for issues
ruff check .

# Run tests
pytest

# Run with verbose output
pytest -v
```