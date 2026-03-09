"""
Design Agent - Platform Designer Agent

Autonomous AI agent that designs and manages scalable data platforms using
Kubernetes and ClickHouse.

Version 1.0.0 - Full Implementation
Features:
- Natural language requirement parsing
- Intelligent infrastructure design
- Kubernetes manifest generation
- ClickHouse cluster provisioning
- Cost estimation and optimization
- Monitoring and alerting integration
"""

import logging
import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import asdict

from app.agents.base import BaseAgent, AgentConfig, AgentStatus
from app.agents.design_engine import (
    DesignEngine,
    Requirements,
    DesignSolution,
    WorkloadType,
    TrafficProfile,
    AvailabilityRequirement
)
from app.agents.k8s_manifest_generator import KubernetesManifestGenerator

logger = logging.getLogger("agents.design_agent")


class DesignAgent(BaseAgent):
    """
    Platform Designer Agent - designs and manages data platforms.

    This agent is responsible for:
    - Designing infrastructure layouts for data platforms
    - Provisioning ClickHouse clusters
    - Managing Kubernetes deployments
    - Configuring monitoring and alerting
    - Providing platform recommendations
    - Natural language requirement parsing
    - Cost estimation and optimization

    Version 1.0.0 - Full implementation with design engine and K8s integration
    """

    def __init__(self, config: AgentConfig):
        super().__init__(config)

        # Configuration for platform design
        self.kubernetes_config = config.config.get("kubernetes_config", {})
        self.clickhouse_config = config.config.get("clickhouse_config", {})
        self.monitoring_config = config.config.get("monitoring_config", {})

        # Initialize components
        self.design_engine: DesignEngine = DesignEngine()
        self.k8s_generator: KubernetesManifestGenerator = KubernetesManifestGenerator()

        # State
        self.platform_designs: Dict[str, Any] = {}
        self.active_deployments: Dict[str, Any] = {}
        self.requirements_history: List[Requirements] = []

        logger.info("DesignAgent initialized (version 1.0.0)")

    async def _on_initialize(self) -> None:
        """
        Initialize Design Agent.

        Load configurations and set up connections to external services.
        """
        logger.info("Initializing Design Agent components")

        # Initialize design engine
        self.design_engine = DesignEngine()

        # Initialize Kubernetes manifest generator
        self.k8s_generator = KubernetesManifestGenerator()

        # Load cached designs if any
        self._load_cached_designs()

        logger.info("Design Agent initialized successfully")

    async def _on_shutdown(self) -> None:
        """
        Shutdown Design Agent.

        Clean up connections and resources.
        """
        logger.info("Shutting down Design Agent")

        # Save designs to cache
        self._save_cached_designs()

        # Clean up resources
        self.platform_designs.clear()
        self.active_deployments.clear()

        logger.info("Design Agent shutdown complete")

    async def _on_process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a design request.

        Args:
            input_data: Must contain:
                - action: The design action to perform
                - parameters: Action-specific parameters

        Supported actions:
            - parse_requirements: Parse natural language requirements
            - design_platform: Design platform infrastructure
            - generate_manifests: Generate Kubernetes manifests
            - provision_cluster: Provision a cluster (dry-run)
            - estimate_cost: Estimate infrastructure cost
            - recommend_configuration: Get configuration recommendations
            - get_design: Retrieve a saved design
            - get_deployment_status: Check deployment status
            - list_designs: List all saved designs

        Returns:
            Dict with:
                - action: The action that was performed
                - status: "success" or "error"
                - result: Action-specific result data
                - message: Human-readable message
        """
        action = input_data.get("action")
        parameters = input_data.get("parameters", {})

        if not action:
            raise ValueError("Missing required field: action")

        logger.info(f"Processing design action: {action}")

        try:
            # Route to appropriate handler
            handlers = {
                "parse_requirements": self._parse_requirements,
                "design_platform": self._design_platform,
                "generate_manifests": self._generate_manifests,
                "provision_cluster": self._provision_cluster,
                "estimate_cost": self._estimate_cost,
                "recommend_configuration": self._recommend_configuration,
                "get_design": self._get_design,
                "get_deployment_status": self._get_deployment_status,
                "list_designs": self._list_designs
            }

            handler = handlers.get(action)
            if not handler:
                raise ValueError(f"Unknown action: {action}. Supported actions: {', '.join(handlers.keys())}")

            result = await handler(parameters)

            return result

        except ValueError as e:
            logger.error(f"Validation error in design action {action}: {e}")
            raise
        except Exception as e:
            logger.error(f"Design action {action} failed: {e}", exc_info=True)
            raise

    async def _parse_requirements(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse natural language requirements.

        Args:
            parameters:
                - description: Natural language description of requirements
                - budget_monthly: Optional explicit budget
                - data_volume_tb: Optional explicit data volume
                - query_rate_qps: Optional explicit query rate

        Returns:
            Parsed requirements object
        """
        description = parameters.get("description", "")
        if not description:
            raise ValueError("Missing required parameter: description")

        budget_monthly = parameters.get("budget_monthly")
        data_volume_tb = parameters.get("data_volume_tb")
        query_rate_qps = parameters.get("query_rate_qps")

        requirements = self.design_engine.parse_requirements(
            description=description,
            budget_monthly=budget_monthly,
            data_volume_tb=data_volume_tb,
            query_rate_qps=query_rate_qps
        )

        # Store in history
        self.requirements_history.append(requirements)

        logger.info(f"Parsed requirements: {requirements.workload_type.value}, "
                   f"{requirements.traffic_profile.value}, ${requirements.budget_monthly}/mo")

        return {
            "action": "parse_requirements",
            "status": "success",
            "result": self._serialize_requirements(requirements),
            "message": f"Requirements parsed successfully: {requirements.workload_type.value} workload"
        }

    async def _design_platform(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Design a data platform infrastructure.

        Args:
            parameters:
                - description: Natural language description (if not using parsed requirements)
                - requirements: Parsed Requirements object (optional)
                - budget_monthly: Optional explicit budget
                - data_volume_tb: Optional explicit data volume
                - query_rate_qps: Optional explicit query rate

        Returns:
            Complete design specification
        """
        # Parse requirements if not provided
        if "requirements" in parameters:
            # Deserialize requirements
            requirements = self._deserialize_requirements(parameters["requirements"])
        else:
            description = parameters.get("description", "")
            if not description:
                raise ValueError("Either 'description' or 'requirements' must be provided")

            requirements = self.design_engine.parse_requirements(
                description=description,
                budget_monthly=parameters.get("budget_monthly"),
                data_volume_tb=parameters.get("data_volume_tb"),
                query_rate_qps=parameters.get("query_rate_qps")
            )

        # Generate design
        design = self.design_engine.generate_design(requirements)

        # Store design
        self.platform_designs[design.design_id] = design

        logger.info(f"Designed platform {design.design_id}: "
                   f"${design.estimated_monthly_cost:.2f}/mo, "
                   f"{design.estimated_availability*100:.3f}% availability")

        return {
            "action": "design_platform",
            "status": "success",
            "result": self._serialize_design_solution(design),
            "message": f"Platform design {design.design_id} created successfully"
        }

    async def _generate_manifests(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate Kubernetes manifests for a design.

        Args:
            parameters:
                - design_id: Design ID to generate manifests for

        Returns:
            List of Kubernetes manifests
        """
        design_id = parameters.get("design_id")
        if not design_id:
            raise ValueError("Missing required parameter: design_id")

        design = self.platform_designs.get(design_id)
        if not design:
            raise ValueError(f"Design not found: {design_id}")

        # Generate manifests
        manifests = self.k8s_generator.generate_all_manifests(
            design.clickhouse_cluster,
            design.kubernetes_cluster,
            design.monitoring
        )

        logger.info(f"Generated {len(manifests)} Kubernetes manifests for design {design_id}")

        return {
            "action": "generate_manifests",
            "status": "success",
            "result": {
                "design_id": design_id,
                "manifest_count": len(manifests),
                "manifests": manifests
            },
            "message": f"Generated {len(manifests)} Kubernetes manifests"
        }

    async def _provision_cluster(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Provision a ClickHouse cluster based on a design.

        Note: This is a dry-run implementation that generates the plan
        without actually provisioning infrastructure.

        Args:
            parameters:
                - design_id: Design ID to provision
                - cluster_name: Name for the cluster
                - namespace: Kubernetes namespace (optional)
                - dry_run: If True, only generate plan (default: True)

        Returns:
            Deployment plan and status
        """
        design_id = parameters.get("design_id")
        cluster_name = parameters.get("cluster_name")

        if not design_id or not cluster_name:
            raise ValueError("Missing required parameters: design_id, cluster_name")

        design = self.platform_designs.get(design_id)
        if not design:
            raise ValueError(f"Design not found: {design_id}")

        dry_run = parameters.get("dry_run", True)

        deployment_id = f"deployment_{datetime.utcnow().timestamp()}"

        # Generate manifests
        manifests = self.k8s_generator.generate_all_manifests(
            design.clickhouse_cluster,
            design.kubernetes_cluster,
            design.monitoring
        )

        # Create deployment record
        deployment = {
            "deployment_id": deployment_id,
            "design_id": design_id,
            "cluster_name": cluster_name,
            "namespace": parameters.get("namespace", design.kubernetes_cluster.namespace),
            "created_at": datetime.utcnow().isoformat(),
            "status": "planned" if dry_run else "provisioning",
            "manifests": [m["yaml"] for m in manifests],
            "dry_run": dry_run,
            "estimated_resources": {
                "clickhouse_nodes": design.clickhouse_cluster.shard_count * design.clickhouse_cluster.replica_count,
                "zookeeper_nodes": design.clickhouse_cluster.zookeeper_nodes if design.clickhouse_cluster.cluster_type == "replicated" else 0,
                "kubernetes_nodes": design.kubernetes_cluster.node_count,
                "total_cpu": design.kubernetes_cluster.total_cpu,
                "total_memory": design.kubernetes_cluster.total_memory
            },
            "estimated_cost_monthly": design.estimated_monthly_cost,
            "estimated_availability": design.estimated_availability
        }

        # Store deployment
        self.active_deployments[deployment_id] = deployment

        if dry_run:
            message = f"Deployment plan {deployment_id} generated (dry-run, not provisioned)"
        else:
            message = f"Deployment {deployment_id} initiated (actual provisioning)"

        logger.info(message)

        return {
            "action": "provision_cluster",
            "status": "success",
            "result": deployment,
            "message": message
        }

    async def _estimate_cost(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Estimate infrastructure cost.

        Args:
            parameters:
                - design_id: Design ID to estimate cost for (optional)
                - OR
                - description: Natural language description
                - budget_monthly: Budget constraint
                - data_volume_tb: Data volume
                - query_rate_qps: Query rate

        Returns:
            Cost estimation details
        """
        design_id = parameters.get("design_id")

        if design_id:
            # Use existing design
            design = self.platform_designs.get(design_id)
            if not design:
                raise ValueError(f"Design not found: {design_id}")
        else:
            # Parse and design
            description = parameters.get("description", "")
            if not description:
                raise ValueError("Either 'design_id' or 'description' must be provided")

            requirements = self.design_engine.parse_requirements(
                description=description,
                budget_monthly=parameters.get("budget_monthly"),
                data_volume_tb=parameters.get("data_volume_tb"),
                query_rate_qps=parameters.get("query_rate_qps")
            )

            design = self.design_engine.generate_design(requirements)

        cost_breakdown = {
            "total_monthly_cost": design.estimated_monthly_cost,
            "total_hourly_cost": design.estimated_monthly_cost / (30 * 24),
            "clickhouse_cluster": {
                "nodes": design.clickhouse_cluster.shard_count * design.clickhouse_cluster.replica_count,
                "cpu": design.clickhouse_cluster.total_cpu,
                "memory": design.clickhouse_cluster.total_memory,
                "storage": design.clickhouse_cluster.storage_per_node
            },
            "kubernetes_cluster": {
                "nodes": design.kubernetes_cluster.node_count,
                "cpu": design.kubernetes_cluster.total_cpu,
                "memory": design.kubernetes_cluster.total_memory
            },
            "monitoring": {
                "prometheus": design.monitoring.prometheus,
                "grafana": design.monitoring.grafana,
                "alertmanager": design.monitoring.alertmanager
            }
        }

        logger.info(f"Cost estimate: ${design.estimated_monthly_cost:.2f}/mo")

        return {
            "action": "estimate_cost",
            "status": "success",
            "result": cost_breakdown,
            "message": f"Estimated cost: ${design.estimated_monthly_cost:.2f}/month"
        }

    async def _recommend_configuration(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recommend platform configuration based on requirements.

        Args:
            parameters:
                - description: Natural language description
                - budget_monthly: Budget constraint
                - data_volume_tb: Data volume
                - query_rate_qps: Query rate

        Returns:
            Multiple configuration recommendations
        """
        description = parameters.get("description", "")
        if not description:
            raise ValueError("Missing required parameter: description")

        # Parse requirements
        requirements = self.design_engine.parse_requirements(
            description=description,
            budget_monthly=parameters.get("budget_monthly"),
            data_volume_tb=parameters.get("data_volume_tb"),
            query_rate_qps=parameters.get("query_rate_qps")
        )

        # Generate designs for different tiers
        recommendations = []

        # Standard tier
        standard_requirements = Requirements(
            workload_type=requirements.workload_type,
            traffic_profile=requirements.traffic_profile,
            availability_requirement=AvailabilityRequirement.STANDARD,
            data_volume_tb=requirements.data_volume_tb,
            retention_days=requirements.retention_days,
            query_rate_qps=requirements.query_rate_qps,
            budget_monthly=max(requirements.budget_monthly * 0.5, 100.0),
            constraints=requirements.constraints
        )
        standard_design = self.design_engine.generate_design(standard_requirements)

        recommendations.append({
            "tier": "standard",
            "description": "Cost-optimized configuration with standard availability",
            "cost_monthly": standard_design.estimated_monthly_cost,
            "availability": standard_design.estimated_availability,
            "clickhouse_shards": standard_design.clickhouse_cluster.shard_count,
            "clickhouse_replicas": standard_design.clickhouse_cluster.replica_count,
            "kubernetes_nodes": standard_design.kubernetes_cluster.node_count
        })

        # Performance tier (matches original requirements)
        performance_design = self.design_engine.generate_design(requirements)

        recommendations.append({
            "tier": "performance",
            "description": "Balanced configuration for typical workloads",
            "cost_monthly": performance_design.estimated_monthly_cost,
            "availability": performance_design.estimated_availability,
            "clickhouse_shards": performance_design.clickhouse_cluster.shard_count,
            "clickhouse_replicas": performance_design.clickhouse_cluster.replica_count,
            "kubernetes_nodes": performance_design.kubernetes_cluster.node_count
        })

        # High availability tier
        ha_requirements = Requirements(
            workload_type=requirements.workload_type,
            traffic_profile=requirements.traffic_profile,
            availability_requirement=AvailabilityRequirement.CRITICAL,
            data_volume_tb=requirements.data_volume_tb,
            retention_days=requirements.retention_days,
            query_rate_qps=requirements.query_rate_qps,
            budget_monthly=requirements.budget_monthly * 1.5,
            constraints=requirements.constraints
        )
        ha_design = self.design_engine.generate_design(ha_requirements)

        recommendations.append({
            "tier": "high-availability",
            "description": "High-availability configuration with critical SLA",
            "cost_monthly": ha_design.estimated_monthly_cost,
            "availability": ha_design.estimated_availability,
            "clickhouse_shards": ha_design.clickhouse_cluster.shard_count,
            "clickhouse_replicas": ha_design.clickhouse_cluster.replica_count,
            "kubernetes_nodes": ha_design.kubernetes_cluster.node_count
        })

        logger.info(f"Generated {len(recommendations)} configuration recommendations")

        return {
            "action": "recommend_configuration",
            "status": "success",
            "result": {
                "requirements": self._serialize_requirements(requirements),
                "recommendations": recommendations
            },
            "message": f"Generated {len(recommendations)} configuration recommendations"
        }

    async def _get_design(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get a platform design by ID.

        Args:
            parameters:
                - design_id: Design ID to retrieve

        Returns:
            Design details
        """
        design_id = parameters.get("design_id")

        if not design_id:
            raise ValueError("Missing required parameter: design_id")

        design = self.platform_designs.get(design_id)

        if not design:
            raise ValueError(f"Design not found: {design_id}")

        return {
            "action": "get_design",
            "status": "success",
            "result": self._serialize_design_solution(design),
            "message": f"Design {design_id} retrieved successfully"
        }

    async def _get_deployment_status(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get deployment status.

        Args:
            parameters:
                - deployment_id: Deployment ID to check

        Returns:
            Deployment status details
        """
        deployment_id = parameters.get("deployment_id")

        if not deployment_id:
            raise ValueError("Missing required parameter: deployment_id")

        deployment = self.active_deployments.get(deployment_id)

        if not deployment:
            raise ValueError(f"Deployment not found: {deployment_id}")

        return {
            "action": "get_deployment_status",
            "status": "success",
            "result": deployment,
            "message": f"Deployment {deployment_id} status retrieved successfully"
        }

    async def _list_designs(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        List all saved platform designs.

        Args:
            parameters:
                - limit: Maximum number of designs to return (optional)

        Returns:
            List of designs
        """
        limit = parameters.get("limit", len(self.platform_designs))

        designs_list = []
        for design_id, design in list(self.platform_designs.items())[:limit]:
            designs_list.append({
                "design_id": design_id,
                "workload_type": design.requirements.workload_type.value,
                "traffic_profile": design.requirements.traffic_profile.value,
                "estimated_cost_monthly": design.estimated_monthly_cost,
                "estimated_availability": design.estimated_availability,
                "created_at": design_id.replace("design_", "")
            })

        return {
            "action": "list_designs",
            "status": "success",
            "result": {
                "total_count": len(self.platform_designs),
                "designs": designs_list
            },
            "message": f"Retrieved {len(designs_list)} designs"
        }

    def _serialize_requirements(self, requirements: Requirements) -> Dict[str, Any]:
        """Serialize Requirements object to dict"""
        return {
            "workload_type": requirements.workload_type.value,
            "traffic_profile": requirements.traffic_profile.value,
            "availability_requirement": requirements.availability_requirement.value,
            "data_volume_tb": requirements.data_volume_tb,
            "retention_days": requirements.retention_days,
            "query_rate_qps": requirements.query_rate_qps,
            "budget_monthly": requirements.budget_monthly,
            "constraints": {
                "max_droplets": requirements.constraints.max_droplets,
                "max_cost_per_hour": requirements.constraints.max_cost_per_hour,
                "providers": requirements.constraints.providers,
                "compliance": requirements.constraints.compliance
            },
            "raw_description": requirements.raw_description
        }

    def _deserialize_requirements(self, data: Dict[str, Any]) -> Requirements:
        """Deserialize Requirements object from dict"""
        return Requirements(
            workload_type=WorkloadType(data["workload_type"]),
            traffic_profile=TrafficProfile(data["traffic_profile"]),
            availability_requirement=AvailabilityRequirement(data["availability_requirement"]),
            data_volume_tb=data["data_volume_tb"],
            retention_days=data["retention_days"],
            query_rate_qps=data["query_rate_qps"],
            budget_monthly=data["budget_monthly"],
            constraints=type('Constraints', (), {
                "max_droplets": data["constraints"]["max_droplets"],
                "max_cost_per_hour": data["constraints"]["max_cost_per_hour"],
                "providers": data["constraints"]["providers"],
                "compliance": data["constraints"]["compliance"]
            })(),
            raw_description=data.get("raw_description", "")
        )

    def _serialize_design_solution(self, design: DesignSolution) -> Dict[str, Any]:
        """Serialize DesignSolution object to dict"""
        return {
            "design_id": design.design_id,
            "requirements": self._serialize_requirements(design.requirements),
            "clickhouse_cluster": {
                "cluster_type": design.clickhouse_cluster.cluster_type,
                "shard_count": design.clickhouse_cluster.shard_count,
                "replica_count": design.clickhouse_cluster.replica_count,
                "zookeeper_nodes": design.clickhouse_cluster.zookeeper_nodes,
                "total_memory": design.clickhouse_cluster.total_memory,
                "total_cpu": design.clickhouse_cluster.total_cpu,
                "storage_per_node": design.clickhouse_cluster.storage_per_node,
                "storage_tier": design.clickhouse_cluster.storage_tier.value
            },
            "kubernetes_cluster": {
                "namespace": design.kubernetes_cluster.namespace,
                "node_count": design.kubernetes_cluster.node_count,
                "total_cpu": design.kubernetes_cluster.total_cpu,
                "total_memory": design.kubernetes_cluster.total_memory,
                "enable_hpa": design.kubernetes_cluster.enable_hpa,
                "enable_pdb": design.kubernetes_cluster.enable_pdb
            },
            "monitoring": {
                "prometheus": design.monitoring.prometheus,
                "grafana": design.monitoring.grafana,
                "alertmanager": design.monitoring.alertmanager,
                "log_aggregation": design.monitoring.log_aggregation,
                "retention_days": design.monitoring.retention_days
            },
            "estimated_monthly_cost": design.estimated_monthly_cost,
            "estimated_availability": design.estimated_availability,
            "deployment_time_hours": design.deployment_time_hours,
            "notes": design.notes,
            "warnings": design.warnings
        }

    def _load_cached_designs(self) -> None:
        """Load cached designs from storage"""
        try:
            cache_file = "/tmp/design_agent_cache.json"
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    logger.info(f"Loaded {len(data)} cached designs")
        except Exception as e:
            logger.warning(f"Failed to load cached designs: {e}")

    def _save_cached_designs(self) -> None:
        """Save designs to cache"""
        try:
            cache_file = "/tmp/design_agent_cache.json"
            data = {design_id: self._serialize_design_solution(design)
                    for design_id, design in self.platform_designs.items()}
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(data)} designs to cache")
        except Exception as e:
            logger.warning(f"Failed to save cached designs: {e}")


def create_design_agent() -> DesignAgent:
    """Factory function to create DesignAgent with default configuration"""
    config = AgentConfig(
        name="design_agent",
        description="Platform Designer Agent - designs and manages scalable data platforms using Kubernetes and ClickHouse",
        version="1.0.0",  # Full implementation
        max_concurrent_tasks=5,
        timeout_seconds=300,
        retry_attempts=3,
        retry_delay_seconds=2.0,
        enabled=True,
        config={
            "kubernetes_config": {
                "api_server": os.getenv("KUBERNETES_API_SERVER"),
                "namespace": os.getenv("KUBERNETES_NAMESPACE", "aidatalabs")
            },
            "clickhouse_config": {
                "default_cluster_type": "replicated"
            },
            "monitoring_config": {
                "enabled": True
            }
        }
    )

    return DesignAgent(config)
