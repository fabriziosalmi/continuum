"""Test module for AuthManager service."""
import pytest
import unittest.mock as mock
import tempfile
import yaml
import os
from unittest.mock import patch, mock_open

from app.services.auth_manager import AuthManager, User


class TestAuthManager:
    """Test class for AuthManager functionality."""

    def setup_method(self):
        """Setup method called before each test."""
        self.auth_manager = AuthManager()

    def test_user_creation(self):
        """Test User dataclass creation."""
        user = User(
            token="test-token",
            name="Test User",
            permissions=["model1", "model2"],
            rate_limit="10/minute"
        )
        assert user.token == "test-token"
        assert user.name == "Test User"
        assert user.permissions == ["model1", "model2"]
        assert user.rate_limit == "10/minute"

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    def test_load_users_success(self, mock_yaml_load, mock_file):
        """Test successful loading of users from YAML file."""
        # Mock YAML content
        mock_yaml_content = {
            "users": [
                {
                    "token": "dev-token",
                    "name": "Developer",
                    "permissions": ["llama3:latest", "gpt-4o"],
                    "rate_limit": "100/minute"
                },
                {
                    "token": "guest-token",
                    "name": "Guest",
                    "permissions": ["llama3:latest"],
                    "rate_limit": "10/minute"
                }
            ]
        }
        mock_yaml_load.return_value = mock_yaml_content

        # Load users
        self.auth_manager.load_users("fake_path.yml")

        # Verify users were loaded correctly
        assert len(self.auth_manager.users) == 2
        assert "dev-token" in self.auth_manager.users
        assert "guest-token" in self.auth_manager.users
        
        dev_user = self.auth_manager.users["dev-token"]
        assert dev_user.name == "Developer"
        assert dev_user.permissions == ["llama3:latest", "gpt-4o"]
        assert dev_user.rate_limit == "100/minute"

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_load_users_file_not_found(self, mock_file):
        """Test handling of missing YAML file."""
        with pytest.raises(FileNotFoundError, match="File di configurazione utenti non trovato"):
            self.auth_manager.load_users("nonexistent.yml")

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load", side_effect=yaml.YAMLError("Invalid YAML"))
    def test_load_users_invalid_yaml(self, mock_yaml_load, mock_file):
        """Test handling of invalid YAML content."""
        with pytest.raises(ValueError, match="Errore nel parsing del file YAML"):
            self.auth_manager.load_users("invalid.yml")

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    def test_load_users_missing_users_section(self, mock_yaml_load, mock_file):
        """Test handling of YAML file without 'users' section."""
        mock_yaml_load.return_value = {"invalid": "structure"}
        
        with pytest.raises(ValueError, match="File di configurazione utenti non valido"):
            self.auth_manager.load_users("invalid_structure.yml")

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    def test_load_users_missing_required_field(self, mock_yaml_load, mock_file):
        """Test handling of users with missing required fields."""
        mock_yaml_content = {
            "users": [
                {
                    "name": "User Without Token",
                    "permissions": ["model1"]
                    # Missing 'token' field
                }
            ]
        }
        mock_yaml_load.return_value = mock_yaml_content

        with pytest.raises(ValueError, match="Campo richiesto mancante"):
            self.auth_manager.load_users("missing_field.yml")

    def test_authenticate_valid_token(self):
        """Test authentication with valid token."""
        # Setup user
        user = User(
            token="valid-token",
            name="Test User",
            permissions=["model1"],
            rate_limit="10/minute"
        )
        self.auth_manager.users["valid-token"] = user

        # Test authentication
        authenticated_user = self.auth_manager.authenticate("valid-token")
        assert authenticated_user is not None
        assert authenticated_user.name == "Test User"
        assert authenticated_user.token == "valid-token"

    def test_authenticate_invalid_token(self):
        """Test authentication with invalid token."""
        authenticated_user = self.auth_manager.authenticate("invalid-token")
        assert authenticated_user is None

    def test_authenticate_empty_token(self):
        """Test authentication with empty token."""
        authenticated_user = self.auth_manager.authenticate("")
        assert authenticated_user is None

    def test_authenticate_none_token(self):
        """Test authentication with None token."""
        authenticated_user = self.auth_manager.authenticate(None)
        assert authenticated_user is None

    def test_is_authorized_valid_permission(self):
        """Test authorization for a model user has permission for."""
        # Setup user with permissions
        user = User(
            token="auth-token",
            name="Auth User",
            permissions=["llama3:latest", "gpt-4o"],
            rate_limit="10/minute"
        )
        self.auth_manager.users["auth-token"] = user

        # Test authorization for allowed model
        assert self.auth_manager.is_authorized("auth-token", "llama3:latest") is True
        assert self.auth_manager.is_authorized("auth-token", "gpt-4o") is True

    def test_is_authorized_invalid_permission(self):
        """Test authorization for a model user doesn't have permission for."""
        # Setup user with limited permissions
        user = User(
            token="limited-token",
            name="Limited User",
            permissions=["llama3:latest"],
            rate_limit="10/minute"
        )
        self.auth_manager.users["limited-token"] = user

        # Test authorization for non-allowed model
        assert self.auth_manager.is_authorized("limited-token", "gpt-4o") is False
        assert self.auth_manager.is_authorized("limited-token", "nonexistent-model") is False

    def test_is_authorized_invalid_token(self):
        """Test authorization with invalid token."""
        assert self.auth_manager.is_authorized("invalid-token", "any-model") is False

    def test_get_user_info_valid_token(self):
        """Test getting user info for valid token."""
        # Setup user
        user = User(
            token="info-token",
            name="Info User",
            permissions=["model1", "model2"],
            rate_limit="50/minute"
        )
        self.auth_manager.users["info-token"] = user

        # Get user info
        user_info = self.auth_manager.get_user_info("info-token")
        assert user_info is not None
        assert user_info["name"] == "Info User"
        assert user_info["permissions"] == ["model1", "model2"]
        assert user_info["rate_limit"] == "50/minute"

    def test_get_user_info_invalid_token(self):
        """Test getting user info for invalid token."""
        user_info = self.auth_manager.get_user_info("invalid-token")
        assert user_info is None

    def test_parse_rate_limit_valid_formats(self):
        """Test parsing of various valid rate limit formats."""
        # Test different time units
        limit, seconds = self.auth_manager._parse_rate_limit("10/minute")
        assert limit == 10
        assert seconds == 60

        limit, seconds = self.auth_manager._parse_rate_limit("100/hour")
        assert limit == 100
        assert seconds == 3600

        limit, seconds = self.auth_manager._parse_rate_limit("5/second")
        assert limit == 5
        assert seconds == 1

        limit, seconds = self.auth_manager._parse_rate_limit("1000/day")
        assert limit == 1000
        assert seconds == 86400

    def test_parse_rate_limit_invalid_format(self):
        """Test parsing of invalid rate limit formats returns safe defaults."""
        # Test invalid format
        limit, seconds = self.auth_manager._parse_rate_limit("invalid_format")
        assert limit == 10  # Default limit
        assert seconds == 60  # Default time (minute)

        # Test unknown time unit
        limit, seconds = self.auth_manager._parse_rate_limit("5/unknown")
        assert limit == 5
        assert seconds == 60  # Default to minute

    @patch("time.time")
    def test_check_rate_limit_within_limit(self, mock_time):
        """Test rate limiting when user is within limits."""
        # Setup mock time
        mock_time.return_value = 1000.0

        # Setup user
        user = User(
            token="rate-token",
            name="Rate User",
            permissions=["model1"],
            rate_limit="5/minute"
        )
        self.auth_manager.users["rate-token"] = user

        # Test requests within limit
        for i in range(5):
            mock_time.return_value = 1000.0 + i  # Advance time slightly
            assert self.auth_manager.check_rate_limit("rate-token") is True

    @patch("time.time")
    def test_check_rate_limit_exceeds_limit(self, mock_time):
        """Test rate limiting when user exceeds limits."""
        # Setup mock time
        mock_time.return_value = 1000.0

        # Setup user with very low rate limit
        user = User(
            token="limited-rate-token",
            name="Limited Rate User",
            permissions=["model1"],
            rate_limit="2/minute"
        )
        self.auth_manager.users["limited-rate-token"] = user

        # Make requests up to limit
        assert self.auth_manager.check_rate_limit("limited-rate-token") is True
        assert self.auth_manager.check_rate_limit("limited-rate-token") is True
        
        # Next request should be denied
        assert self.auth_manager.check_rate_limit("limited-rate-token") is False

    @patch("time.time")
    def test_check_rate_limit_resets_after_time_window(self, mock_time):
        """Test that rate limit resets after time window passes."""
        # Setup user
        user = User(
            token="reset-token",
            name="Reset User",
            permissions=["model1"],
            rate_limit="1/minute"
        )
        self.auth_manager.users["reset-token"] = user

        # First request at time 1000
        mock_time.return_value = 1000.0
        assert self.auth_manager.check_rate_limit("reset-token") is True

        # Second request immediately should be denied
        assert self.auth_manager.check_rate_limit("reset-token") is False

        # After time window passes, should be allowed again
        mock_time.return_value = 1070.0  # 70 seconds later (> 1 minute)
        assert self.auth_manager.check_rate_limit("reset-token") is True

    def test_check_rate_limit_invalid_token(self):
        """Test rate limiting with invalid token."""
        assert self.auth_manager.check_rate_limit("invalid-token") is False

    def test_load_users_with_defaults(self):
        """Test loading users with default values."""
        with patch("builtins.open", mock_open()), \
             patch("yaml.safe_load") as mock_yaml_load:
            
            # Mock YAML content with some default values
            mock_yaml_content = {
                "users": [
                    {
                        "token": "minimal-token",
                        "name": "Minimal User"
                        # Missing permissions and rate_limit - should use defaults
                    }
                ]
            }
            mock_yaml_load.return_value = mock_yaml_content

            # Load users
            self.auth_manager.load_users("test.yml")

            # Verify defaults were applied
            user = self.auth_manager.users["minimal-token"]
            assert user.permissions == []  # Default empty list
            assert user.rate_limit == "10/minute"  # Default rate limit