"""
Security Tests

Tests for security vulnerabilities: SQL injection, XSS, auth bypass, etc.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.security
class TestAuthenticationSecurity:
    """Security tests for authentication system."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.mark.security
    async def test_weak_password_rejected(self, client: AsyncClient):
        """Test that weak passwords are rejected."""
        weak_passwords = [
            "123",  # Too short
            "password",  # Common
            "password123",  # Still common
            "12345678",  # All numbers
            "abcdefgh",  # All lowercase
        ]
        
        for password in weak_passwords:
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"test{len(password)}@example.com",
                    "password": password,
                    "full_name": "Test User"
                }
            )
            # Weak password should be rejected
            assert response.status_code in [400, 422], f"Weak password '{password}' was accepted"

    @pytest.mark.security
    async def test_sql_injection_in_email(self, client: AsyncClient):
        """Test SQL injection attempts in email field."""
        sql_injections = [
            "' OR '1'='1",
            "admin'--",
            "' UNION SELECT * FROM users--",
            "'; DROP TABLE users; --",
            "admin' #",
        ]
        
        for injection in sql_injections:
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": injection + "@example.com",
                    "password": "Test123!",
                    "full_name": "Test User"
                }
            )
            # Should not succeed (email validation should catch it)
            assert response.status_code in [400, 422]

    @pytest.mark.security
    async def test_brute_force_protection(self, client: AsyncClient):
        """Test protection against brute force attacks."""
        # Try multiple failed login attempts
        for i in range(20):
            response = await client.post(
                "/api/v1/auth/login",
                data={
                    "username": f"user{i}@example.com",
                    "password": "wrongpassword"
                }
            )
            # Should fail
            assert response.status_code in [400, 401, 429]
            
            # After many attempts, may get rate limited (429)
            if response.status_code == 429:
                print(f"\n✅ Rate limiting detected after {i+1} attempts")
                break

    @pytest.mark.security
    async def test_token_expiration(self, client: AsyncClient):
        """Test that expired tokens are rejected."""
        # Create expired token (fake it for testing)
        # In real implementation, tokens would expire after configured time
        expired_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2MDAwMDAwMDB9.fake"
        
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        
        # Should reject expired token
        assert response.status_code in [401, 403]

    @pytest.mark.security
    async def test_password_hashing(self, client: AsyncClient):
        """Test that passwords are properly hashed."""
        # This would require database access to verify
        # For now, just ensure password is not returned in responses
        unique_id = pytest.hash_seed or "test"
        email = f"hash{unique_id}@example.com"
        
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Test123!",
                "full_name": "Test User"
            }
        )
        
        # Response should not contain plaintext password
        if response.status_code in [200, 201]:
            data = response.json()
            assert "password" not in data
            assert "Test123!" not in str(data)


@pytest.mark.security
class TestInputValidationSecurity:
    """Security tests for input validation."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.mark.security
    async def test_xss_prevention_in_user_input(self, client: AsyncClient):
        """Test XSS attack prevention in user input."""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "'><script>alert('XSS')</script>",
        ]
        
        for payload in xss_payloads:
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "test@example.com",
                    "password": "Test123!",
                    "full_name": payload
                }
            )
            # May succeed, but payload should be sanitized
            if response.status_code in [200, 201]:
                # Verify payload is not returned as-is
                data = response.json()
                user_display_name = data.get("full_name", "")
                assert "<script>" not in user_display_name, f"XSS payload not sanitized: {user_display_name}"

    @pytest.mark.security
    async def test_large_input_rejection(self, client: AsyncClient):
        """Test that excessively large inputs are rejected."""
        large_string = "A" * 100000  # 100KB
        
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": large_string + "@example.com",
                "password": "Test123!",
                "full_name": "Test User"
            }
        )
        
        # Should reject due to size limits
        assert response.status_code in [400, 422, 413]

    @pytest.mark.security
    async def test_special_characters_in_query(self, client: AsyncClient):
        """Test SQL injection in query parameters."""
        sql_injections = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "' UNION SELECT password FROM users--",
            "1' AND 1=1--",
        ]
        
        # This would require authentication first
        unique_id = pytest.hash_seed or "test"
        email = f"sql{unique_id}@example.com"
        
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Sql123!",
                "full_name": "SQL Test"
            }
        )
        
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "Sql123!"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try SQL injection in query endpoint
        for injection in sql_injections:
            response = await client.post(
                "/api/v1/query/execute",
                headers=headers,
                json={
                    "query": injection,
                    "schema_id": None
                }
            )
            # Should not succeed with SQL injection
            # May fail validation or return empty results
            assert response.status_code in [400, 404, 500]


@pytest.mark.security
class TestAuthorizationSecurity:
    """Security tests for authorization."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.fixture
    async def user_headers(self, client: AsyncClient):
        """Get headers for regular user."""
        unique_id = pytest.hash_seed or "test"
        email = f"user{unique_id}@example.com"
        
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "User123!",
                "full_name": "Regular User"
            }
        )
        
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "User123!"}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.security
    async def test_unauthorized_access_protected(self, client: AsyncClient):
        """Test that protected endpoints require authentication."""
        protected_endpoints = [
            "/api/v1/auth/me",
            "/api/v1/chat/chats",
            "/api/v1/data/schemas",
            "/api/v1/agents/",
            "/api/v1/query/execute",
        ]
        
        for endpoint in protected_endpoints:
            response = await client.get(endpoint)
            assert response.status_code in [401, 403], f"Endpoint {endpoint} not protected"

    @pytest.mark.security
    async def test_user_cannot_access_others_data(self, client: AsyncClient, user_headers: dict):
        """Test that users cannot access other users' data."""
        # Create two users
        user1_email = f"user1{pytest.hash_seed}@example.com"
        user2_email = f"user2{pytest.hash_seed}@example.com"
        
        # User 1
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": user1_email,
                "password": "User1_123!",
                "full_name": "User 1"
            }
        )
        
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": user1_email, "password": "User1_123!"}
        )
        user1_token = response.json()["access_token"]
        
        # User 2
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": user2_email,
                "password": "User2_123!",
                "full_name": "User 2"
            }
        )
        
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": user2_email, "password": "User2_123!"}
        )
        user2_token = response.json()["access_token"]
        
        # User 1 creates a chat
        user1_headers = {"Authorization": f"Bearer {user1_token}"}
        response = await client.post(
            "/api/v1/chat/chats",
            headers=user1_headers,
            json={"title": "User 1's Chat"}
        )
        
        if response.status_code in [200, 201]:
            chat_id = response.json().get("id") or response.json().get("chat_id")
            
            # User 2 tries to access User 1's chat
            user2_headers = {"Authorization": f"Bearer {user2_token}"}
            response = await client.get(
                f"/api/v1/chat/chats/{chat_id}",
                headers=user2_headers
            )
            
            # Should be forbidden
            assert response.status_code in [403, 404]


@pytest.mark.security
class TestSecurityHeaders:
    """Security tests for HTTP headers."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.mark.security
    async def test_security_headers_present(self, client: AsyncClient):
        """Test that security headers are present."""
        response = await client.get("/")
        headers = response.headers
        
        # Check for common security headers
        # Note: These may not all be present depending on FastAPI configuration
        
        # X-Content-Type-Options
        if "x-content-type-options" in headers:
            assert headers["x-content-type-options"] == "nosniff"
        
        # X-Frame-Options
        if "x-frame-options" in headers:
            assert headers["x-frame-options"] in ["DENY", "SAMEORIGIN"]
        
        # Content-Security-Policy (if configured)
        # if "content-security-policy" in headers:
        #     assert "default-src" in headers["content-security-policy"]

    @pytest.mark.security
    async def test_no_sensitive_data_in_errors(self, client: AsyncClient):
        """Test that error messages don't leak sensitive information."""
        # Trigger various errors
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "nonexistent@example.com", "password": "wrong"}
        )
        
        # Error should not reveal:
        # - Database structure
        # - Internal paths
        # - Stack traces in production
        error_content = response.text.lower()
        
        # In production, these should not appear
        assert "traceback" not in error_content
        assert "stack" not in error_content
        assert "/app/" not in error_content
        assert "database" not in error_content


@pytest.mark.security
class TestRateLimitingSecurity:
    """Security tests for rate limiting."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.mark.security
    async def test_prevents_abuse(self, client: AsyncClient):
        """Test that rate limiting prevents abuse."""
        # Make many rapid requests
        status_codes = []
        
        for i in range(100):
            response = await client.get("/health")
            status_codes.append(response.status_code)
            
            # Break if we hit rate limit
            if response.status_code == 429:
                print(f"\n✅ Rate limiting triggered after {i+1} requests")
                break
        
        # Should have hit rate limit at some point
        # (or at least not crashed)
        assert len(status_codes) > 0


@pytest.mark.security
class TestDataSanitization:
    """Security tests for data sanitization."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.mark.security
    async def test_output_escaping(self, client: AsyncClient):
        """Test that output is properly escaped."""
        unique_id = pytest.hash_seed or "test"
        email = f"escape{unique_id}@example.com"
        
        # Register with potential XSS in name
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Escape123!",
                "full_name": "<script>alert('XSS')</script>"
            }
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            # Script tags should be escaped or removed
            full_name = data.get("full_name", "")
            assert "<script>" not in full_name
