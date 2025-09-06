"""Test module for HTTP Bridge server."""

import json
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from app.bridge.http_server import HTTPServer
from app.services.auth_manager import AuthManager, User
from app.services.model_router import ModelRouter
from app.providers.base_provider import BaseProvider


class MockProvider(BaseProvider):
    """Mock provider for testing."""

    def __init__(self, response_chunks=None):
        self.response_chunks = response_chunks or ["Hello", " world", "!"]

    async def stream_completion(self, messages, settings):
        """Mock stream completion."""
        for chunk in self.response_chunks:
            yield chunk


class TestHTTPServer:
    """Test class for HTTP Server functionality."""

    def setup_method(self):
        """Setup method called before each test."""
        # Create mock auth manager
        self.mock_auth_manager = Mock(spec=AuthManager)
        self.mock_auth_manager.users = {}

        # Create mock model router
        self.mock_model_router = Mock(spec=ModelRouter)

        # Create HTTP server with mocked dependencies
        self.http_server = HTTPServer(self.mock_auth_manager, self.mock_model_router)
        self.client = TestClient(self.http_server.app)

    def test_health_check(self):
        """Test health check endpoint."""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_list_models_no_auth(self):
        """Test listing models without authentication."""
        response = self.client.get("/v1/models")
        assert response.status_code == 401  # Missing Authorization header

    def test_list_models_invalid_auth_format(self):
        """Test listing models with invalid auth header format."""
        response = self.client.get(
            "/v1/models", headers={"Authorization": "InvalidFormat token"}
        )
        assert response.status_code == 401
        assert "Invalid authorization header format" in response.json()["detail"]

    def test_list_models_invalid_token(self):
        """Test listing models with invalid token."""
        # Mock authentication failure
        self.mock_auth_manager.authenticate.return_value = None

        response = self.client.get(
            "/v1/models", headers={"Authorization": "Bearer invalid-token"}
        )
        assert response.status_code == 401
        assert "Invalid authentication token" in response.json()["detail"]

    def test_list_models_success(self):
        """Test successful listing of models."""
        # Setup mock user
        mock_user = User(
            token="valid-token",
            name="Test User",
            permissions=["model1", "model2"],
            rate_limit="10/minute",
        )
        self.mock_auth_manager.authenticate.return_value = mock_user
        self.mock_auth_manager.is_authorized.side_effect = (
            lambda token, model: model in ["model1", "model2"]
        )

        # Setup mock available models
        self.mock_model_router.get_available_models.return_value = [
            "model1",
            "model2",
            "model3",
        ]

        response = self.client.get(
            "/v1/models", headers={"Authorization": "Bearer valid-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) == 2  # Only authorized models

        model_ids = [model["id"] for model in data["data"]]
        assert "model1" in model_ids
        assert "model2" in model_ids
        assert "model3" not in model_ids  # Not authorized

    def test_chat_completions_no_auth(self):
        """Test chat completions without authentication."""
        request_data = {
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}],
        }

        response = self.client.post("/v1/chat/completions", json=request_data)
        assert response.status_code == 401  # Missing Authorization header

    def test_chat_completions_invalid_token(self):
        """Test chat completions with invalid token."""
        self.mock_auth_manager.authenticate.return_value = None

        request_data = {
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}],
        }

        response = self.client.post(
            "/v1/chat/completions",
            json=request_data,
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert response.status_code == 401
        assert "Invalid authentication token" in response.json()["detail"]

    def test_chat_completions_rate_limit_exceeded(self):
        """Test chat completions when rate limit is exceeded."""
        # Setup mock user but rate limit exceeded
        mock_user = User(
            token="rate-limited-token",
            name="Rate Limited User",
            permissions=["test-model"],
            rate_limit="1/minute",
        )
        self.mock_auth_manager.authenticate.return_value = mock_user
        self.mock_auth_manager.check_rate_limit.return_value = False

        request_data = {
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}],
        }

        response = self.client.post(
            "/v1/chat/completions",
            json=request_data,
            headers={"Authorization": "Bearer rate-limited-token"},
        )

        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["detail"]

    def test_chat_completions_unauthorized_model(self):
        """Test chat completions with unauthorized model."""
        # Setup mock user without permission for requested model
        mock_user = User(
            token="unauthorized-token",
            name="Unauthorized User",
            permissions=["allowed-model"],
            rate_limit="10/minute",
        )
        self.mock_auth_manager.authenticate.return_value = mock_user
        self.mock_auth_manager.check_rate_limit.return_value = True
        self.mock_auth_manager.is_authorized.return_value = False

        request_data = {
            "model": "forbidden-model",
            "messages": [{"role": "user", "content": "Hello"}],
        }

        response = self.client.post(
            "/v1/chat/completions",
            json=request_data,
            headers={"Authorization": "Bearer unauthorized-token"},
        )

        assert response.status_code == 403
        assert (
            "User not authorized to use model: forbidden-model"
            in response.json()["detail"]
        )

    def test_chat_completions_model_not_found(self):
        """Test chat completions with non-existent model."""
        # Setup authorized user
        mock_user = User(
            token="valid-token",
            name="Valid User",
            permissions=["nonexistent-model"],
            rate_limit="10/minute",
        )
        self.mock_auth_manager.authenticate.return_value = mock_user
        self.mock_auth_manager.check_rate_limit.return_value = True
        self.mock_auth_manager.is_authorized.return_value = True
        self.mock_model_router.get_provider_for_model.return_value = None

        request_data = {
            "model": "nonexistent-model",
            "messages": [{"role": "user", "content": "Hello"}],
        }

        response = self.client.post(
            "/v1/chat/completions",
            json=request_data,
            headers={"Authorization": "Bearer valid-token"},
        )

        assert response.status_code == 404
        assert "Model not found: nonexistent-model" in response.json()["detail"]

    def test_chat_completions_non_streaming_success(self):
        """Test successful non-streaming chat completion."""
        # Setup authorized user
        mock_user = User(
            token="valid-token",
            name="Valid User",
            permissions=["test-model"],
            rate_limit="10/minute",
        )
        self.mock_auth_manager.authenticate.return_value = mock_user
        self.mock_auth_manager.check_rate_limit.return_value = True
        self.mock_auth_manager.is_authorized.return_value = True

        # Setup mock provider
        mock_provider = MockProvider(["Hello", " world"])
        self.mock_model_router.get_provider_for_model.return_value = mock_provider

        request_data = {
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False,
            "temperature": 0.7,
            "max_tokens": 100,
        }

        response = self.client.post(
            "/v1/chat/completions",
            json=request_data,
            headers={"Authorization": "Bearer valid-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "chat.completion"
        assert data["model"] == "test-model"
        assert len(data["choices"]) == 1
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert data["choices"][0]["message"]["content"] == "Hello world"
        assert data["choices"][0]["finish_reason"] == "stop"

    def test_chat_completions_streaming_success(self):
        """Test successful streaming chat completion."""
        # Setup authorized user
        mock_user = User(
            token="valid-token",
            name="Valid User",
            permissions=["test-model"],
            rate_limit="10/minute",
        )
        self.mock_auth_manager.authenticate.return_value = mock_user
        self.mock_auth_manager.check_rate_limit.return_value = True
        self.mock_auth_manager.is_authorized.return_value = True

        # Setup mock provider
        mock_provider = MockProvider(["Hello", " streaming"])
        self.mock_model_router.get_provider_for_model.return_value = mock_provider

        request_data = {
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }

        response = self.client.post(
            "/v1/chat/completions",
            json=request_data,
            headers={"Authorization": "Bearer valid-token"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Parse SSE response
        sse_lines = response.text.strip().split("\n\n")
        data_lines = [line for line in sse_lines if line.startswith("data: ")]

        # Should have chunks for "Hello", " streaming", final chunk, and [DONE]
        assert len(data_lines) >= 3

        # Check first chunk
        first_chunk = json.loads(data_lines[0].replace("data: ", ""))
        assert first_chunk["object"] == "chat.completion.chunk"
        assert first_chunk["model"] == "test-model"
        assert first_chunk["choices"][0]["delta"]["content"] == "Hello"

    def test_chat_completions_provider_error(self):
        """Test chat completion with provider error."""
        # Setup authorized user
        mock_user = User(
            token="valid-token",
            name="Valid User",
            permissions=["error-model"],
            rate_limit="10/minute",
        )
        self.mock_auth_manager.authenticate.return_value = mock_user
        self.mock_auth_manager.check_rate_limit.return_value = True
        self.mock_auth_manager.is_authorized.return_value = True

        # Setup mock provider that raises an error
        mock_provider = Mock()

        async def failing_stream(*args, **kwargs):
            raise Exception("Provider error")
            yield  # Never reached

        mock_provider.stream_completion = failing_stream
        self.mock_model_router.get_provider_for_model.return_value = mock_provider

        request_data = {
            "model": "error-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False,
        }

        response = self.client.post(
            "/v1/chat/completions",
            json=request_data,
            headers={"Authorization": "Bearer valid-token"},
        )

        assert response.status_code == 500
        assert "Error generating completion" in response.json()["detail"]

    def test_chat_completions_with_all_settings(self):
        """Test chat completion with all possible settings."""
        # Setup authorized user
        mock_user = User(
            token="valid-token",
            name="Valid User",
            permissions=["full-settings-model"],
            rate_limit="10/minute",
        )
        self.mock_auth_manager.authenticate.return_value = mock_user
        self.mock_auth_manager.check_rate_limit.return_value = True
        self.mock_auth_manager.is_authorized.return_value = True

        # Setup mock provider
        mock_provider = MockProvider(["Response"])
        self.mock_model_router.get_provider_for_model.return_value = mock_provider

        request_data = {
            "model": "full-settings-model",
            "messages": [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hello"},
            ],
            "stream": False,
            "temperature": 0.8,
            "max_tokens": 150,
            "top_p": 0.9,
            "frequency_penalty": 0.5,
            "presence_penalty": 0.3,
            "stop": ["END"],
        }

        response = self.client.post(
            "/v1/chat/completions",
            json=request_data,
            headers={"Authorization": "Bearer valid-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "full-settings-model"
        assert data["choices"][0]["message"]["content"] == "Response"

    def test_invalid_json_request(self):
        """Test handling of invalid JSON in request."""
        response = self.client.post(
            "/v1/chat/completions",
            data="invalid json",
            headers={
                "Authorization": "Bearer valid-token",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 422  # Validation error

    def test_missing_required_fields(self):
        """Test handling of missing required fields in request."""
        # Missing 'messages' field
        request_data = {"model": "test-model"}

        response = self.client.post(
            "/v1/chat/completions",
            json=request_data,
            headers={"Authorization": "Bearer valid-token"},
        )

        assert response.status_code == 422  # Validation error

    def test_invalid_message_format(self):
        """Test handling of invalid message format."""
        request_data = {
            "model": "test-model",
            "messages": [
                {"invalid": "format"}  # Missing 'role' and 'content'
            ],
        }

        response = self.client.post(
            "/v1/chat/completions",
            json=request_data,
            headers={"Authorization": "Bearer valid-token"},
        )

        assert response.status_code == 422  # Validation error

    def test_dashboard_endpoint(self):
        """Test dashboard endpoint."""
        response = self.client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_metrics_endpoint(self):
        """Test metrics endpoint."""
        with patch("app.services.enhanced_logging.enhanced_logger") as mock_logger:
            mock_logger.get_metrics_summary.return_value = {
                "requests_last_hour": 100,
                "average_response_time": 0.5,
                "error_summary": {},
                "model_usage": {},
            }

            response = self.client.get("/metrics")
            assert response.status_code == 200
            data = response.json()
            assert "requests_last_hour" in data

    def test_detailed_metrics_endpoint(self):
        """Test detailed metrics endpoint."""
        with patch("app.services.enhanced_logging.enhanced_logger") as mock_logger:
            mock_logger.get_detailed_metrics.return_value = [{"request": "data"}]
            mock_logger.get_metrics_summary.return_value = {"total": 1}

            response = self.client.get("/metrics/detailed?limit=50")
            assert response.status_code == 200
            data = response.json()
            assert "metrics" in data
            assert "summary" in data

    def test_admin_status_endpoint_unauthorized(self):
        """Test admin status endpoint without admin permissions."""
        # Setup non-admin user
        mock_user = User(
            token="user-token",
            name="Regular User",
            permissions=["model1"],
            rate_limit="10/minute",
        )
        self.mock_auth_manager.authenticate.return_value = mock_user

        response = self.client.get(
            "/admin/status", headers={"Authorization": "Bearer user-token"}
        )

        assert response.status_code == 403
        assert "Admin access required" in response.json()["detail"]

    def test_admin_status_endpoint_authorized(self):
        """Test admin status endpoint with admin permissions."""
        # Setup admin user
        mock_user = User(
            token="admin-token",
            name="Administrator",
            permissions=["model1"],
            rate_limit="100/minute",
        )
        self.mock_auth_manager.authenticate.return_value = mock_user
        self.mock_auth_manager.users = {"admin-token": mock_user}
        self.mock_auth_manager.rate_limit_tracker = {}
        self.mock_model_router.get_available_models.return_value = ["model1"]
        self.mock_model_router.get_model_config.return_value = {"provider": "ollama"}

        with (
            patch("app.services.enhanced_logging.enhanced_logger") as mock_logger,
            patch.object(
                self.http_server,
                "_get_memory_usage",
                return_value={"rss_mb": 100, "cpu_percent": 5.0},
            ),
        ):
            mock_logger.get_metrics_summary.return_value = {"requests": 100}

            response = self.client.get(
                "/admin/status", headers={"Authorization": "Bearer admin-token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "system" in data
            assert "models" in data
            assert "users" in data
            assert "metrics" in data
