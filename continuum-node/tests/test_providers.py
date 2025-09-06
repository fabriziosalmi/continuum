"""Test module for Provider classes."""

import pytest
import aiohttp
import json
from unittest.mock import patch, Mock, AsyncMock

from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_provider import OpenAIProvider


class AsyncIteratorMock:
    """Mock async iterator for testing."""

    def __init__(self, data):
        self.data = data
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.data):
            raise StopAsyncIteration
        value = self.data[self.index]
        self.index += 1
        return value


class TestOllamaProvider:
    """Test class for OllamaProvider functionality."""

    def setup_method(self):
        """Setup method called before each test."""
        self.provider = OllamaProvider()

    def test_init_default_url(self):
        """Test initialization with default base URL."""
        provider = OllamaProvider()
        assert provider.base_url == "http://localhost:11434"

    @patch.dict("os.environ", {"OLLAMA_BASE_URL": "http://custom-host:8080"})
    def test_init_custom_url(self):
        """Test initialization with custom base URL from environment."""
        provider = OllamaProvider()
        assert provider.base_url == "http://custom-host:8080"

    @pytest.mark.asyncio
    async def test_stream_completion_success(self):
        """Test successful streaming completion from Ollama."""
        messages = [{"role": "user", "content": "Hello"}]
        settings = {"model": "llama3:latest", "temperature": 0.7}

        # Mock response data
        mock_responses = [
            json.dumps({"message": {"content": "Hello"}, "done": False}).encode(
                "utf-8"
            ),
            json.dumps({"message": {"content": " there"}, "done": False}).encode(
                "utf-8"
            ),
            json.dumps({"message": {"content": "!"}, "done": True}).encode("utf-8"),
        ]

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.content = AsyncIteratorMock(mock_responses)
            mock_post.return_value.__aenter__.return_value = mock_response

            # Collect stream results
            chunks = []
            async for chunk in self.provider.stream_completion(messages, settings):
                chunks.append(chunk)

            # Verify results
            assert chunks == ["Hello", " there", "!"]

    @pytest.mark.asyncio
    async def test_stream_completion_with_settings(self):
        """Test streaming completion with various settings."""
        messages = [{"role": "user", "content": "Test"}]
        settings = {
            "model": "custom-model",
            "temperature": 0.8,
            "max_tokens": 100,
            "top_p": 0.9,
        }

        mock_response_data = json.dumps(
            {"message": {"content": "Response"}, "done": True}
        ).encode("utf-8")

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.content = AsyncIteratorMock([mock_response_data])
            mock_post.return_value.__aenter__.return_value = mock_response

            # Process stream
            chunks = []
            async for chunk in self.provider.stream_completion(messages, settings):
                chunks.append(chunk)

            # Verify the request was made with correct payload
            mock_post.assert_called_once()
            call_args = mock_post.call_args

            # Check the JSON payload
            expected_payload = {
                "model": "custom-model",
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": 0.8,
                    "num_predict": 100,  # max_tokens mapped to num_predict
                    "top_p": 0.9,
                },
            }
            assert call_args[1]["json"] == expected_payload

    @pytest.mark.asyncio
    async def test_stream_completion_api_error(self):
        """Test handling of API error responses."""
        messages = [{"role": "user", "content": "Test"}]
        settings = {"model": "llama3:latest"}

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = Mock()
            mock_response.status = 500
            mock_response.text = AsyncMock(return_value="Internal Server Error")
            mock_post.return_value.__aenter__.return_value = mock_response

            with pytest.raises(Exception, match="Ollama API error 500"):
                async for chunk in self.provider.stream_completion(messages, settings):
                    pass

    @pytest.mark.asyncio
    async def test_stream_completion_network_error(self):
        """Test handling of network errors."""
        messages = [{"role": "user", "content": "Test"}]
        settings = {"model": "llama3:latest"}

        with patch(
            "aiohttp.ClientSession.post",
            side_effect=aiohttp.ClientError("Network error"),
        ):
            with pytest.raises(Exception, match="Network error connecting to Ollama"):
                async for chunk in self.provider.stream_completion(messages, settings):
                    pass

    @pytest.mark.asyncio
    async def test_stream_completion_invalid_json(self):
        """Test handling of invalid JSON in response."""
        messages = [{"role": "user", "content": "Test"}]
        settings = {"model": "llama3:latest"}

        # Mock response with invalid JSON
        invalid_responses = [
            b"invalid json",
            json.dumps({"message": {"content": "valid"}, "done": True}).encode("utf-8"),
        ]

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.content = AsyncIteratorMock(invalid_responses)
            mock_post.return_value.__aenter__.return_value = mock_response

            # Should only get valid chunks, invalid JSON should be ignored
            chunks = []
            async for chunk in self.provider.stream_completion(messages, settings):
                chunks.append(chunk)

            assert chunks == ["valid"]

    @pytest.mark.asyncio
    async def test_stream_completion_empty_content(self):
        """Test handling of empty content in chunks."""
        messages = [{"role": "user", "content": "Test"}]
        settings = {"model": "llama3:latest"}

        # Mock responses with empty content
        mock_responses = [
            json.dumps({"message": {"content": ""}, "done": False}).encode("utf-8"),
            json.dumps(
                {"message": {"content": "actual content"}, "done": False}
            ).encode("utf-8"),
            json.dumps({"message": {"content": ""}, "done": True}).encode("utf-8"),
        ]

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.content = AsyncIteratorMock(mock_responses)
            mock_post.return_value.__aenter__.return_value = mock_response

            chunks = []
            async for chunk in self.provider.stream_completion(messages, settings):
                chunks.append(chunk)

            # Should only get non-empty content
            assert chunks == ["actual content"]


class TestOpenAIProvider:
    """Test class for OpenAIProvider functionality."""

    def setup_method(self):
        """Setup method called before each test."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-api-key"}):
            self.provider = OpenAIProvider()

    def test_init_with_api_key(self):
        """Test initialization with API key from environment."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            provider = OpenAIProvider()
            assert provider.api_key == "test-key"
            assert provider.base_url == "https://api.openai.com/v1"

    def test_init_without_api_key(self):
        """Test initialization without API key."""
        with patch.dict("os.environ", {}, clear=True):
            provider = OpenAIProvider()
            assert provider.api_key is None

    @pytest.mark.asyncio
    async def test_stream_completion_success(self):
        """Test successful streaming completion from OpenAI."""
        messages = [{"role": "user", "content": "Hello"}]
        settings = {"model": "gpt-4o", "temperature": 0.7}

        # Mock SSE response data
        mock_responses = [
            (
                "data: "
                + json.dumps(
                    {
                        "choices": [
                            {"delta": {"content": "Hello"}, "finish_reason": None}
                        ]
                    }
                )
                + "\n"
            ).encode("utf-8"),
            (
                "data: "
                + json.dumps(
                    {
                        "choices": [
                            {"delta": {"content": " world"}, "finish_reason": None}
                        ]
                    }
                )
                + "\n"
            ).encode("utf-8"),
            (
                "data: "
                + json.dumps({"choices": [{"delta": {}, "finish_reason": "stop"}]})
                + "\n"
            ).encode("utf-8"),
            b"data: [DONE]\n",
        ]

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.content = AsyncIteratorMock(mock_responses)
            mock_post.return_value.__aenter__.return_value = mock_response

            # Collect stream results
            chunks = []
            async for chunk in self.provider.stream_completion(messages, settings):
                chunks.append(chunk)

            # Verify results
            assert chunks == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_stream_completion_no_api_key(self):
        """Test streaming completion without API key."""
        provider = OpenAIProvider()
        provider.api_key = None

        messages = [{"role": "user", "content": "Test"}]
        settings = {"model": "gpt-4o"}

        with pytest.raises(
            ValueError, match="OPENAI_API_KEY environment variable is required"
        ):
            async for chunk in provider.stream_completion(messages, settings):
                pass

    @pytest.mark.asyncio
    async def test_stream_completion_with_settings(self):
        """Test streaming completion with various settings."""
        messages = [{"role": "user", "content": "Test"}]
        settings = {
            "model": "gpt-3.5-turbo",
            "temperature": 0.8,
            "max_tokens": 100,
            "top_p": 0.9,
            "frequency_penalty": 0.5,
            "presence_penalty": 0.3,
        }

        mock_response_data = (
            "data: "
            + json.dumps(
                {
                    "choices": [
                        {"delta": {"content": "Response"}, "finish_reason": "stop"}
                    ]
                }
            )
            + "\n"
        ).encode("utf-8")

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.content = AsyncIteratorMock(
                [mock_response_data, b"data: [DONE]\n"]
            )
            mock_post.return_value.__aenter__.return_value = mock_response

            # Process stream
            chunks = []
            async for chunk in self.provider.stream_completion(messages, settings):
                chunks.append(chunk)

            # Verify the request was made with correct payload
            mock_post.assert_called_once()
            call_args = mock_post.call_args

            expected_payload = {
                "model": "gpt-3.5-turbo",
                "messages": messages,
                "stream": True,
                "temperature": 0.8,
                "max_tokens": 100,
                "top_p": 0.9,
                "frequency_penalty": 0.5,
                "presence_penalty": 0.3,
            }
            assert call_args[1]["json"] == expected_payload

            # Verify headers
            expected_headers = {
                "Authorization": "Bearer test-api-key",
                "Content-Type": "application/json",
            }
            assert call_args[1]["headers"] == expected_headers

    @pytest.mark.asyncio
    async def test_stream_completion_api_error(self):
        """Test handling of API error responses."""
        messages = [{"role": "user", "content": "Test"}]
        settings = {"model": "gpt-4o"}

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = Mock()
            mock_response.status = 429
            mock_response.text = AsyncMock(return_value="Rate limit exceeded")
            mock_post.return_value.__aenter__.return_value = mock_response

            with pytest.raises(Exception, match="OpenAI API error 429"):
                async for chunk in self.provider.stream_completion(messages, settings):
                    pass

    @pytest.mark.asyncio
    async def test_stream_completion_network_error(self):
        """Test handling of network errors."""
        messages = [{"role": "user", "content": "Test"}]
        settings = {"model": "gpt-4o"}

        with patch(
            "aiohttp.ClientSession.post",
            side_effect=aiohttp.ClientError("Network error"),
        ):
            with pytest.raises(Exception, match="Network error connecting to OpenAI"):
                async for chunk in self.provider.stream_completion(messages, settings):
                    pass

    @pytest.mark.asyncio
    async def test_stream_completion_invalid_sse(self):
        """Test handling of invalid Server-Sent Events format."""
        messages = [{"role": "user", "content": "Test"}]
        settings = {"model": "gpt-4o"}

        # Mock response with invalid SSE format
        invalid_responses = [
            b"invalid sse line\n",
            b": this is a comment\n",
            b"\n",  # empty line
            (
                "data: "
                + json.dumps(
                    {
                        "choices": [
                            {"delta": {"content": "valid"}, "finish_reason": "stop"}
                        ]
                    }
                )
                + "\n"
            ).encode("utf-8"),
            b"data: [DONE]\n",
        ]

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.content = AsyncIteratorMock(invalid_responses)
            mock_post.return_value.__aenter__.return_value = mock_response

            chunks = []
            async for chunk in self.provider.stream_completion(messages, settings):
                chunks.append(chunk)

            # Should only get valid content
            assert chunks == ["valid"]

    @pytest.mark.asyncio
    async def test_stream_completion_invalid_json_in_sse(self):
        """Test handling of invalid JSON in SSE data lines."""
        messages = [{"role": "user", "content": "Test"}]
        settings = {"model": "gpt-4o"}

        # Mock response with invalid JSON in data lines
        responses = [
            b"data: invalid json\n",
            (
                "data: "
                + json.dumps(
                    {
                        "choices": [
                            {"delta": {"content": "valid"}, "finish_reason": None}
                        ]
                    }
                )
                + "\n"
            ).encode("utf-8"),
            b"data: [DONE]\n",
        ]

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.content = AsyncIteratorMock(responses)
            mock_post.return_value.__aenter__.return_value = mock_response

            chunks = []
            async for chunk in self.provider.stream_completion(messages, settings):
                chunks.append(chunk)

            # Should only get valid content, invalid JSON should be ignored
            assert chunks == ["valid"]

    @pytest.mark.asyncio
    async def test_stream_completion_missing_delta_content(self):
        """Test handling of responses without delta content."""
        messages = [{"role": "user", "content": "Test"}]
        settings = {"model": "gpt-4o"}

        responses = [
            (
                "data: "
                + json.dumps(
                    {
                        "choices": [{"delta": {}, "finish_reason": None}]  # No content
                    }
                )
                + "\n"
            ).encode("utf-8"),
            (
                "data: "
                + json.dumps(
                    {
                        "choices": [
                            {
                                "delta": {"content": "actual content"},
                                "finish_reason": None,
                            }
                        ]
                    }
                )
                + "\n"
            ).encode("utf-8"),
            (
                "data: "
                + json.dumps(
                    {
                        "choices": [
                            {"delta": {"content": ""}, "finish_reason": None}
                        ]  # Empty content
                    }
                )
                + "\n"
            ).encode("utf-8"),
            b"data: [DONE]\n",
        ]

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.content = AsyncIteratorMock(responses)
            mock_post.return_value.__aenter__.return_value = mock_response

            chunks = []
            async for chunk in self.provider.stream_completion(messages, settings):
                chunks.append(chunk)

            # Should only get non-empty content
            assert chunks == ["actual content"]
