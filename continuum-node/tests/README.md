# Continuum Node Tests

This directory contains comprehensive unit and integration tests for the Continuum Node project.

## Test Structure

- **test_auth_manager.py** - Tests for user authentication, authorization, and rate limiting
- **test_model_router.py** - Tests for model routing and provider management  
- **test_providers.py** - Tests for AI provider integrations (Ollama, OpenAI)
- **test_http_bridge.py** - Integration tests for the FastAPI HTTP server

## Running Tests

### Prerequisites

Install the test dependencies:
```bash
pip install pytest pytest-asyncio httpx aioresponses
```

### Run All Tests
```bash
pytest tests/
```

### Run Specific Test Files
```bash
pytest tests/test_auth_manager.py
pytest tests/test_providers.py
```

### Run with Coverage (if coverage is installed)
```bash
pytest tests/ --cov=app --cov-report=html
```

### Verbose Output
```bash
pytest tests/ -v
```

## Test Coverage

The test suite provides comprehensive coverage for:

- ✅ Authentication and authorization flows
- ✅ Rate limiting functionality  
- ✅ Model routing and provider instantiation
- ✅ HTTP API endpoints and error handling
- ✅ Streaming and non-streaming responses
- ✅ External API integration mocking
- ✅ Configuration file loading and validation
- ✅ Edge cases and error scenarios

## Test Configuration

Tests are configured via `pytest.ini` with:
- Async test support enabled
- Proper test discovery patterns
- Short traceback format for cleaner output

## Mocking Strategy

Tests use appropriate mocking:
- `unittest.mock` for basic mocking and patching
- `aioresponses` for HTTP request mocking  
- Custom `AsyncIteratorMock` for streaming response simulation
- FastAPI `TestClient` for HTTP endpoint testing

All tests are isolated and do not require external dependencies or network access.