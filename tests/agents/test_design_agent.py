"""
Design Agent Tests

Comprehensive tests for the Platform Designer Agent.
"""

import pytest
import asyncio
from datetime import datetime

from app.agents.design_agent import create_design_agent
from app.agents.design_engine import (
    WorkloadType,
    TrafficProfile,
    AvailabilityRequirement
)


@pytest.fixture
def design_agent():
    """Create a design agent instance"""
    agent = create_design_agent()
    # Initialize agent (usually done in _on_initialize)
    asyncio.run(agent._on_initialize())
    yield agent
    # Cleanup
    asyncio.run(agent._on_shutdown())


class TestRequirementParsing:
    """Tests for natural language requirement parsing"""

    @pytest.mark.asyncio
    async def test_parse_realtime_analytics_requirements(self, design_agent):
        """Test parsing requirements for real-time analytics"""
        result = await design_agent._parse_requirements({
            "description": "I need a real-time analytics platform with 10TB of data, handling about 1000 queries per second, with high availability. My budget is $1000 per month."
        })

        assert result["status"] == "success"
        assert result["result"]["workload_type"] == WorkloadType.REALTIME_ANALYTICS.value
        assert result["result"]["data_volume_tb"] == 10.0
        assert result["result"]["query_rate_qps"] == 1000
        assert result["result"]["availability_requirement"] == AvailabilityRequirement.HIGH.value
        assert result["result"]["budget_monthly"] == 1000.0

    @pytest.mark.asyncio
    async def test_parse_time_series_requirements(self, design_agent):
        """Test parsing requirements for time-series data"""
        result = await design_agent._parse_requirements({
            "description": "Need time-series database for IoT metrics. 5TB data, medium traffic, standard availability. Budget: $500/month"
        })

        assert result["status"] == "success"
        assert result["result"]["workload_type"] == WorkloadType.TIME_SERIES.value
        assert result["result"]["data_volume_tb"] == 5.0
        assert result["result"]["availability_requirement"] == AvailabilityRequirement.STANDARD.value

    @pytest.mark.asyncio
    async def test_parse_clickstream_requirements(self, design_agent):
        """Test parsing requirements for clickstream analytics"""
        result = await design_agent._parse_requirements({
            "description": "Web analytics platform for clickstream data. 20TB, high traffic, critical availability."
        })

        assert result["status"] == "success"
        assert result["result"]["workload_type"] == WorkloadType.CLICKSTREAM.value
        assert result["result"]["availability_requirement"] == AvailabilityRequirement.CRITICAL.value

    @pytest.mark.asyncio
    async def test_parse_with_explicit_parameters(self, design_agent):
        """Test parsing with explicit parameters overriding natural language"""
        result = await design_agent._parse_requirements({
            "description": "A data platform",
            "budget_monthly": 2000.0,
            "data_volume_tb": 15.0,
            "query_rate_qps": 5000
        })

        assert result["status"] == "success"
        assert result["result"]["budget_monthly"] == 2000.0
        assert result["result"]["data_volume_tb"] == 15.0
        assert result["result"]["query_rate_qps"] == 5000


class TestPlatformDesign:
    """Tests for platform infrastructure design"""

    @pytest.mark.asyncio
    async def test_design_realtime_analytics_platform(self, design_agent):
        """Test designing a real-time analytics platform"""
        result = await design_agent._design_platform({
            "description": "Real-time analytics platform with 10TB data, 1000 QPS, high availability, $1000 budget"
        })

        assert result["status"] == "success"
        assert "design_id" in result["result"]

        design = result["result"]
        assert "clickhouse_cluster" in design
        assert "kubernetes_cluster" in design
        assert "monitoring" in design
        assert "estimated_monthly_cost" in design
        assert "estimated_availability" in design

        # Verify ClickHouse configuration
        ch = design["clickhouse_cluster"]
        assert ch["cluster_type"] == "replicated"
        assert ch["shard_count"] >= 2
        assert ch["replica_count"] >= 2
        assert ch["zookeeper_nodes"] >= 3

        # Verify Kubernetes configuration
        k8s = design["kubernetes_cluster"]
        assert k8s["node_count"] >= 3
        assert k8s["enable_hpa"] == True  # High traffic should enable HPA

    @pytest.mark.asyncio
    async def test_design_with_cost_constraint(self, design_agent):
        """Test design with strict budget constraint"""
        result = await design_agent._design_platform({
            "description": "Low-cost analytics platform with 5TB data, standard availability",
            "budget_monthly": 200.0
        })

        assert result["status"] == "success"
        design = result["result"]

        # Should warn if cost exceeds budget
        assert design["estimated_monthly_cost"] <= 300.0  # Some tolerance

    @pytest.mark.asyncio
    async def test_design_critical_availability(self, design_agent):
        """Test design with critical availability requirement"""
        result = await design_agent._design_platform({
            "description": "Mission-critical analytics with extreme availability requirements"
        })

        assert result["status"] == "success"
        design = result["result"]

        # Critical availability should have higher replica count
        ch = design["clickhouse_cluster"]
        assert ch["replica_count"] >= 3

        # Should have PDB enabled
        k8s = design["kubernetes_cluster"]
        assert k8s["enable_pdb"] == True

        # Estimated availability should be high
        assert design["estimated_availability"] >= 0.9995


class TestKubernetesManifests:
    """Tests for Kubernetes manifest generation"""

    @pytest.mark.asyncio
    async def test_generate_manifests_for_design(self, design_agent):
        """Test generating Kubernetes manifests for a design"""
        # First create a design
        design_result = await design_agent._design_platform({
            "description": "Analytics platform with 10TB data, high availability"
        })

        design_id = design_result["result"]["design_id"]

        # Generate manifests
        manifests_result = await design_agent._generate_manifests({
            "design_id": design_id
        })

        assert manifests_result["status"] == "success"
        assert manifests_result["result"]["manifest_count"] > 0

        manifests = manifests_result["result"]["manifests"]

        # Check for essential manifest types
        manifest_types = [m["type"] for m in manifests]
        assert "Namespace" in manifest_types
        assert "ConfigMap" in manifest_types
        assert "StatefulSet" in manifest_types
        assert "Service" in manifest_types

    @pytest.mark.asyncio
    async def test_manifest_yaml_validity(self, design_agent):
        """Test that generated YAML is valid"""
        design_result = await design_agent._design_platform({
            "description": "Simple analytics platform"
        })

        design_id = design_result["result"]["design_id"]

        manifests_result = await design_agent._generate_manifests({
            "design_id": design_id
        })

        manifests = manifests_result["result"]["manifests"]

        # Check that each manifest has valid YAML
        for manifest in manifests:
            yaml = manifest["yaml"]
            assert "apiVersion:" in yaml
            assert "kind:" in yaml
            assert "metadata:" in yaml


class TestCostEstimation:
    """Tests for cost estimation"""

    @pytest.mark.asyncio
    async def test_estimate_cost_for_description(self, design_agent):
        """Test cost estimation from natural language"""
        result = await design_agent._estimate_cost({
            "description": "Analytics platform with 5TB data, medium traffic",
            "budget_monthly": 500.0
        })

        assert result["status"] == "success"
        assert "total_monthly_cost" in result["result"]
        assert "total_hourly_cost" in result["result"]
        assert "clickhouse_cluster" in result["result"]
        assert "kubernetes_cluster" in result["result"]

        # Cost should be reasonable
        monthly_cost = result["result"]["total_monthly_cost"]
        assert 50.0 <= monthly_cost <= 2000.0

    @pytest.mark.asyncio
    async def test_estimate_cost_for_existing_design(self, design_agent):
        """Test cost estimation for existing design"""
        # Create design first
        design_result = await design_agent._design_platform({
            "description": "Analytics platform with 10TB data"
        })

        design_id = design_result["result"]["design_id"]

        # Estimate cost
        cost_result = await design_agent._estimate_cost({
            "design_id": design_id
        })

        assert cost_result["status"] == "success"
        assert cost_result["result"]["total_monthly_cost"] > 0


class TestConfigurationRecommendations:
    """Tests for configuration recommendations"""

    @pytest.mark.asyncio
    async def test_generate_recommendations(self, design_agent):
        """Test generating multiple configuration recommendations"""
        result = await design_agent._recommend_configuration({
            "description": "Analytics platform with 10TB data, high traffic",
            "budget_monthly": 1000.0
        })

        assert result["status"] == "success"
        assert "recommendations" in result["result"]

        recommendations = result["result"]["recommendations"]
        assert len(recommendations) >= 3  # Should have at least 3 tiers

        # Check that each recommendation has required fields
        for rec in recommendations:
            assert "tier" in rec
            assert "cost_monthly" in rec
            assert "availability" in rec
            assert "clickhouse_shards" in rec
            assert "clickhouse_replicas" in rec
            assert "kubernetes_nodes" in rec

        # Check tiers
        tiers = [rec["tier"] for rec in recommendations]
        assert "standard" in tiers
        assert "performance" in tiers
        assert "high-availability" in tiers

        # Check that costs are ordered
        costs = [rec["cost_monthly"] for rec in recommendations]
        assert costs[0] <= costs[1] <= costs[2]


class TestDeploymentPlanning:
    """Tests for deployment planning (dry-run)"""

    @pytest.mark.asyncio
    async def test_provision_cluster_dry_run(self, design_agent):
        """Test cluster provisioning in dry-run mode"""
        # Create design
        design_result = await design_agent._design_platform({
            "description": "Analytics platform with 5TB data"
        })

        design_id = design_result["result"]["design_id"]

        # Provision in dry-run mode
        provision_result = await design_agent._provision_cluster({
            "design_id": design_id,
            "cluster_name": "test-cluster",
            "dry_run": True
        })

        assert provision_result["status"] == "success"
        assert provision_result["result"]["dry_run"] == True
        assert provision_result["result"]["status"] == "planned"

        deployment = provision_result["result"]
        assert "deployment_id" in deployment
        assert "estimated_resources" in deployment
        assert "manifests" in deployment
        assert len(deployment["manifests"]) > 0

    @pytest.mark.asyncio
    async def test_provision_with_custom_namespace(self, design_agent):
        """Test provisioning with custom namespace"""
        design_result = await design_agent._design_platform({
            "description": "Analytics platform"
        })

        design_id = design_result["result"]["design_id"]

        provision_result = await design_agent._provision_cluster({
            "design_id": design_id,
            "cluster_name": "test-cluster",
            "namespace": "custom-namespace",
            "dry_run": True
        })

        assert provision_result["result"]["namespace"] == "custom-namespace"


class TestDesignRetrieval:
    """Tests for design retrieval and listing"""

    @pytest.mark.asyncio
    async def test_get_design_by_id(self, design_agent):
        """Test retrieving a design by ID"""
        # Create design
        design_result = await design_agent._design_platform({
            "description": "Test analytics platform"
        })

        design_id = design_result["result"]["design_id"]

        # Retrieve design
        get_result = await design_agent._get_design({
            "design_id": design_id
        })

        assert get_result["status"] == "success"
        assert get_result["result"]["design_id"] == design_id
        assert "clickhouse_cluster" in get_result["result"]
        assert "kubernetes_cluster" in get_result["result"]

    @pytest.mark.asyncio
    async def test_get_nonexistent_design(self, design_agent):
        """Test retrieving a non-existent design"""
        with pytest.raises(ValueError, match="Design not found"):
            await design_agent._get_design({
                "design_id": "nonexistent"
            })

    @pytest.mark.asyncio
    async def test_list_designs(self, design_agent):
        """Test listing all designs"""
        # Create a few designs
        await design_agent._design_platform({
            "description": "Design 1"
        })
        await design_agent._design_platform({
            "description": "Design 2"
        })

        # List designs
        list_result = await design_agent._list_designs({})

        assert list_result["status"] == "success"
        assert list_result["result"]["total_count"] >= 2
        assert len(list_result["result"]["designs"]) >= 2

        # Check design structure
        for design in list_result["result"]["designs"]:
            assert "design_id" in design
            assert "workload_type" in design
            assert "estimated_cost_monthly" in design
            assert "estimated_availability" in design


class TestErrorHandling:
    """Tests for error handling"""

    @pytest.mark.asyncio
    async def test_missing_required_parameter(self, design_agent):
        """Test error when required parameter is missing"""
        with pytest.raises(ValueError, match="Missing required parameter"):
            await design_agent._parse_requirements({})

    @pytest.mark.asyncio
    async def test_invalid_action(self, design_agent):
        """Test error for invalid action"""
        result = await design_agent._on_process({
            "action": "invalid_action",
            "parameters": {}
        })

        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_provision_nonexistent_design(self, design_agent):
        """Test provisioning with non-existent design"""
        with pytest.raises(ValueError, match="Design not found"):
            await design_agent._provision_cluster({
                "design_id": "nonexistent",
                "cluster_name": "test"
            })


class TestIntegration:
    """Integration tests for complete workflows"""

    @pytest.mark.asyncio
    async def test_full_design_workflow(self, design_agent):
        """Test complete workflow from parsing to manifest generation"""
        # 1. Parse requirements
        parse_result = await design_agent._parse_requirements({
            "description": "Real-time analytics with 10TB data, 1000 QPS, high availability, $1000 budget"
        })
        assert parse_result["status"] == "success"

        # 2. Design platform
        design_result = await design_agent._design_platform({
            "description": "Real-time analytics with 10TB data, 1000 QPS, high availability, $1000 budget"
        })
        assert design_result["status"] == "success"
        design_id = design_result["result"]["design_id"]

        # 3. Generate manifests
        manifests_result = await design_agent._generate_manifests({
            "design_id": design_id
        })
        assert manifests_result["status"] == "success"
        assert manifests_result["result"]["manifest_count"] > 0

        # 4. Provision (dry-run)
        provision_result = await design_agent._provision_cluster({
            "design_id": design_id,
            "cluster_name": "test-cluster",
            "dry_run": True
        })
        assert provision_result["status"] == "success"

    @pytest.mark.asyncio
    async def test_cost_optimization_workflow(self, design_agent):
        """Test workflow for cost optimization"""
        # Get recommendations
        rec_result = await design_agent._recommend_configuration({
            "description": "Analytics platform with 5TB data",
            "budget_monthly": 800.0
        })

        recommendations = rec_result["result"]["recommendations"]

        # Find most cost-effective option that meets requirements
        standard = next(r for r in recommendations if r["tier"] == "standard")

        # Verify it's within budget
        assert standard["cost_monthly"] <= 800.0

    @pytest.mark.asyncio
    async def test_high_availability_workflow(self, design_agent):
        """Test workflow for high availability design"""
        design_result = await design_agent._design_platform({
            "description": "Mission-critical platform with extreme availability"
        })

        design = design_result["result"]

        # Verify high availability features
        assert design["estimated_availability"] >= 0.9995
        assert design["clickhouse_cluster"]["replica_count"] >= 3
        assert design["kubernetes_cluster"]["enable_pdb"] == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
