"""
Load and Performance Tests

Tests for performance characteristics and load handling capacity.
"""

import pytest
import asyncio
import time
from httpx import AsyncClient, ASGITransport
from app.main import app
from typing import List


@pytest.mark.performance
class TestAPIPerformance:
    """Performance tests for API endpoints."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.mark.performance
    async def test_health_check_performance(self, client: AsyncClient):
        """Test health check endpoint performance."""
        iterations = 100
        times = []
        
        for _ in range(iterations):
            start = time.time()
            response = await client.get("/health")
            end = time.time()
            
            assert response.status_code == 200
            times.append((end - start) * 1000)
        
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        p95_time = sorted(times)[int(len(times) * 0.95)]
        p99_time = sorted(times)[int(len(times) * 0.99)]
        
        print(f"\n📊 Health Check Performance ({iterations} requests):")
        print(f"   Average: {avg_time:.2f}ms")
        print(f"   Min: {min_time:.2f}ms")
        print(f"   Max: {max_time:.2f}ms")
        print(f"   P95: {p95_time:.2f}ms")
        print(f"   P99: {p99_time:.2f}ms")
        
        # Performance assertions
        assert avg_time < 50, f"Average response time too high: {avg_time:.2f}ms"
        assert p95_time < 100, f"P95 response time too high: {p95_time:.2f}ms"
        assert p99_time < 200, f"P99 response time too high: {p99_time:.2f}ms"

    @pytest.mark.performance
    async def test_concurrent_health_checks(self, client: AsyncClient):
        """Test concurrent health check requests."""
        concurrent_requests = 50
        start = time.time()
        
        tasks = [client.get("/health") for _ in range(concurrent_requests)]
        responses = await asyncio.gather(*tasks)
        
        end = time.time()
        total_time = end - start
        avg_time_per_request = (total_time / concurrent_requests) * 1000
        requests_per_second = concurrent_requests / total_time
        
        # Verify all succeeded
        for response in responses:
            assert response.status_code == 200
        
        print(f"\n📊 Concurrent Health Checks ({concurrent_requests} requests):")
        print(f"   Total time: {total_time:.2f}s")
        print(f"   Avg per request: {avg_time_per_request:.2f}ms")
        print(f"   Requests/second: {requests_per_second:.2f}")
        
        # Performance assertions
        assert requests_per_second > 100, f"Throughput too low: {requests_per_second:.2f} req/s"

    @pytest.mark.performance
    async def test_authentication_performance(self, client: AsyncClient):
        """Test authentication performance."""
        unique_id = pytest.hash_seed or "test"
        email = f"perf{unique_id}@example.com"
        
        # Test registration
        start = time.time()
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Perf123!",
                "full_name": "Performance User"
            }
        )
        registration_time = (time.time() - start) * 1000
        assert response.status_code in [200, 201]
        
        # Test login (multiple times)
        login_times = []
        for _ in range(10):
            start = time.time()
            response = await client.post(
                "/api/v1/auth/login",
                data={"username": email, "password": "Perf123!"}
            )
            end = time.time()
            assert response.status_code == 200
            login_times.append((end - start) * 1000)
        
        avg_login_time = sum(login_times) / len(login_times)
        
        print(f"\n📊 Authentication Performance:")
        print(f"   Registration: {registration_time:.2f}ms")
        print(f"   Login (avg of 10): {avg_login_time:.2f}ms")
        
        # Performance assertions
        assert avg_login_time < 300, f"Login too slow: {avg_login_time:.2f}ms"


@pytest.mark.load
class TestLoadHandling:
    """Load tests for system capacity."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.mark.load
    async def test_sustained_load(self, client: AsyncClient):
        """Test sustained load over time."""
        duration_seconds = 30
        requests_per_second = 10
        total_requests = duration_seconds * requests_per_second
        
        success_count = 0
        error_count = 0
        response_times = []
        
        start_time = time.time()
        
        for i in range(total_requests):
            request_start = time.time()
            
            # Make request
            response = await client.get("/health")
            
            request_end = time.time()
            response_time = (request_end - request_start) * 1000
            
            if response.status_code == 200:
                success_count += 1
                response_times.append(response_time)
            else:
                error_count += 1
            
            # Maintain request rate
            expected_time = i / requests_per_second
            actual_time = request_end - start_time
            if actual_time < expected_time:
                await asyncio.sleep(expected_time - actual_time)
        
        actual_duration = time.time() - start_time
        
        # Calculate metrics
        success_rate = (success_count / total_requests) * 100
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        p95_response_time = sorted(response_times)[int(len(response_times) * 0.95)] if response_times else 0
        p99_response_time = sorted(response_times)[int(len(response_times) * 0.99)] if response_times else 0
        
        print(f"\n📊 Sustained Load Test ({actual_duration:.1f}s, {total_requests} requests):")
        print(f"   Success rate: {success_rate:.2f}%")
        print(f"   Avg response time: {avg_response_time:.2f}ms")
        print(f"   P95 response time: {p95_response_time:.2f}ms")
        print(f"   P99 response time: {p99_response_time:.2f}ms")
        
        # Load assertions
        assert success_rate > 99, f"Success rate too low: {success_rate:.2f}%"
        assert avg_response_time < 100, f"Avg response time too high: {avg_response_time:.2f}ms"

    @pytest.mark.load
    async def test_spike_load(self, client: AsyncClient):
        """Test handling of sudden load spikes."""
        spike_size = 100
        
        # Baseline
        baseline_start = time.time()
        await client.get("/health")
        baseline_time = (time.time() - baseline_start) * 1000
        
        # Spike
        spike_start = time.time()
        tasks = [client.get("/health") for _ in range(spike_size)]
        responses = await asyncio.gather(*tasks)
        spike_time = (time.time() - spike_start) * 1000
        
        # Verify all succeeded
        success_count = sum(1 for r in responses if r.status_code == 200)
        
        # Response times during spike
        spike_response_times = []
        for response in responses:
            # Note: httpx doesn't provide exact timing for async responses
            # This is a simplified metric
            if response.status_code == 200:
                spike_response_times.append(spike_time / spike_size)
        
        avg_spike_time = sum(spike_response_times) / len(spike_response_times) if spike_response_times else 0
        
        print(f"\n📊 Spike Load Test ({spike_size} concurrent requests):")
        print(f"   Baseline: {baseline_time:.2f}ms")
        print(f"   Spike total: {spike_time:.2f}ms")
        print(f"   Spike avg per request: {avg_spike_time:.2f}ms")
        print(f"   Success rate: {(success_count/spike_size)*100:.2f}%")
        
        # Load assertions
        assert success_count >= spike_size * 0.99, f"Too many failures during spike: {success_count}/{spike_size}"

    @pytest.mark.load
    async def test_gradual_ramp_up(self, client: AsyncClient):
        """Test gradual ramp-up of load."""
        stages = [
            (5, 10),    # 5 concurrent requests, 10 times
            (10, 10),   # 10 concurrent requests, 10 times
            (20, 10),   # 20 concurrent requests, 10 times
            (50, 5),    # 50 concurrent requests, 5 times
        ]
        
        results = []
        
        for concurrent, iterations in stages:
            stage_times = []
            
            for _ in range(iterations):
                start = time.time()
                
                tasks = [client.get("/health") for _ in range(concurrent)]
                responses = await asyncio.gather(*tasks)
                
                end = time.time()
                stage_times.append((end - start) * 1000)
                
                # Verify all succeeded
                for response in responses:
                    assert response.status_code == 200
            
            avg_stage_time = sum(stage_times) / len(stage_times)
            avg_per_request = avg_stage_time / concurrent
            results.append((concurrent, avg_stage_time, avg_per_request))
            
            print(f"\n📊 Ramp-up Stage ({concurrent} concurrent):")
            print(f"   Avg stage time: {avg_stage_time:.2f}ms")
            print(f"   Avg per request: {avg_per_request:.2f}ms")
        
        # Check for degradation (response times shouldn't increase linearly with load)
        first_avg = results[0][2]
        last_avg = results[-1][2]
        degradation_ratio = last_avg / first_avg
        
        print(f"\n📊 Ramp-up Summary:")
        print(f"   First stage avg: {first_avg:.2f}ms")
        print(f"   Last stage avg: {last_avg:.2f}ms")
        print(f"   Degradation ratio: {degradation_ratio:.2f}x")
        
        # Should not degrade more than 10x
        assert degradation_ratio < 10, f"Too much degradation: {degradation_ratio:.2f}x"


@pytest.mark.performance
class TestDatabasePerformance:
    """Performance tests for database operations."""

    @pytest.fixture
    async def authenticated_client(self, client: AsyncClient):
        """Create authenticated client."""
        unique_id = pytest.hash_seed or "test"
        email = f"dbperf{unique_id}@example.com"
        
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "DbPerf123!",
                "full_name": "DB Perf User"
            }
        )
        
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "DbPerf123!"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        return headers

    @pytest.mark.performance
    async def test_chat_listing_performance(self, client: AsyncClient, authenticated_client: dict):
        """Test chat listing performance."""
        times = []
        
        for _ in range(50):
            start = time.time()
            response = await client.get("/api/v1/chat/chats", headers=authenticated_client)
            end = time.time()
            
            assert response.status_code == 200
            times.append((end - start) * 1000)
        
        avg_time = sum(times) / len(times)
        p95_time = sorted(times)[int(len(times) * 0.95)]
        
        print(f"\n📊 Chat Listing Performance:")
        print(f"   Average: {avg_time:.2f}ms")
        print(f"   P95: {p95_time:.2f}ms")
        
        # Database queries should be fast
        assert avg_time < 100, f"Chat listing too slow: {avg_time:.2f}ms"


@pytest.mark.performance
class TestMemoryUsage:
    """Performance tests for memory usage."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    @pytest.mark.performance
    async def test_memory_stability(self, client: AsyncClient):
        """Test that memory usage remains stable over time."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Make many requests
        for _ in range(100):
            await client.get("/health")
            await client.get("/api/v1/agents/")  # May fail, but that's ok
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        print(f"\n📊 Memory Usage:")
        print(f"   Initial: {initial_memory:.2f}MB")
        print(f"   Final: {final_memory:.2f}MB")
        print(f"   Increase: {memory_increase:.2f}MB")
        
        # Memory increase should be reasonable (< 50MB for 100 requests)
        assert memory_increase < 50, f"Memory leak detected: {memory_increase:.2f}MB increase"


def pytest_generate_tests(metafunc):
    """Generate parametrized tests for load testing."""
    if "concurrency_level" in metafunc.fixturenames:
        metafunc.parametrize(
            "concurrency_level",
            [1, 5, 10, 20, 50],
            ids=["1 concurrent", "5 concurrent", "10 concurrent", "20 concurrent", "50 concurrent"]
        )
