"""
Design Engine - Core infrastructure design logic for Platform Designer Agent.

This module provides the decision engine that analyzes requirements and
generates optimal infrastructure designs.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re

logger = logging.getLogger("agents.design_engine")


class WorkloadType(Enum):
    """Types of workloads supported"""
    WEB_APPLICATION = "web_application"
    MICROSERVICES = "microservices"
    BATCH_PROCESSING = "batch_processing"
    REALTIME_ANALYTICS = "realtime_analytics"
    TIME_SERIES = "time_series"
    CLICKSTREAM = "clickstream"
    UNKNOWN = "unknown"


class TrafficProfile(Enum):
    """Traffic intensity profiles"""
    LOW = "low"        # < 100 QPS
    MEDIUM = "medium"  # 100-1000 QPS
    HIGH = "high"      # 1000-10000 QPS
    EXTREME = "extreme"  # > 10000 QPS


class AvailabilityRequirement(Enum):
    """Availability requirements"""
    STANDARD = "standard"      # 99.5% (3.65 days/year downtime)
    HIGH = "high"             # 99.9% (8.76 hours/year downtime)
    CRITICAL = "critical"     # 99.95% (4.38 hours/year downtime)
    EXTREME = "extreme"       # 99.99% (52.56 minutes/year downtime)


class StorageTier(Enum):
    """Storage tier options"""
    STANDARD = "standard"      # HDD, lower cost
    SSD = "ssd"               # SSD, balanced
    NVME = "nvme"              # NVMe, highest performance


@dataclass
class InfrastructureConstraints:
    """Constraints for infrastructure design"""
    max_droplets: int = 10
    max_cost_per_hour: float = 1.0
    providers: List[str] = field(default_factory=lambda: ["digitalocean"])
    compliance: List[str] = field(default_factory=list)
    regions: List[str] = field(default_factory=lambda: ["sgp1", "nyc3", "ams3"])


@dataclass
class Requirements:
    """Parsed infrastructure requirements"""
    workload_type: WorkloadType
    traffic_profile: TrafficProfile
    availability_requirement: AvailabilityRequirement
    data_volume_tb: float
    retention_days: int
    query_rate_qps: int
    budget_monthly: float
    constraints: InfrastructureConstraints = field(default_factory=InfrastructureConstraints)
    raw_description: str = ""


@dataclass
class ClickHouseClusterSpec:
    """ClickHouse cluster specification"""
    cluster_type: str = "replicated"  # replicated, standalone
    shard_count: int = 3
    replica_count: int = 2
    zookeeper_nodes: int = 3
    total_memory: str = "48Gi"
    total_cpu: str = "12 cores"
    storage_per_node: str = "1TB"
    storage_tier: StorageTier = StorageTier.SSD


@dataclass
class KubernetesClusterSpec:
    """Kubernetes cluster specification"""
    namespace: str = "aidatalabs"
    node_count: int = 6
    total_cpu: str = "12 cores"
    total_memory: str = "48Gi"
    enable_hpa: bool = True  # Horizontal Pod Autoscaler
    enable_pdb: bool = False  # Pod Disruption Budget


@dataclass
class MonitoringSpec:
    """Monitoring specification"""
    prometheus: bool = True
    grafana: bool = True
    alertmanager: bool = True
    log_aggregation: bool = True
    retention_days: int = 30


@dataclass
class DesignSolution:
    """Complete infrastructure design solution"""
    design_id: str
    requirements: Requirements
    clickhouse_cluster: ClickHouseClusterSpec
    kubernetes_cluster: KubernetesClusterSpec
    monitoring: MonitoringSpec
    estimated_monthly_cost: float
    estimated_availability: float
    deployment_time_hours: float
    notes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class DesignEngine:
    """
    Core design engine for infrastructure optimization.

    Uses multi-objective optimization to balance cost, performance, and availability.
    """

    # Configuration constants
    MIN_BUDGET = 50.0  # Minimum realistic monthly budget in USD
    DEFAULT_RETENTION_DAYS = 30

    # ClickHouse sizing rules (in TB)
    SHARD_SIZE_TB = 5.0  # Max data per shard

    # Cost estimation (per hour USD)
    COST_PER_CORE = 0.05
    COST_PER_GB_RAM = 0.01
    COST_PER_TB_SSD = 0.02

    def __init__(self):
        self.design_cache: Dict[str, DesignSolution] = {}

    def parse_requirements(
        self,
        description: str,
        budget_monthly: Optional[float] = None,
        data_volume_tb: Optional[float] = None,
        query_rate_qps: Optional[int] = None
    ) -> Requirements:
        """
        Parse natural language description into structured requirements.

        Args:
            description: Natural language description of requirements
            budget_monthly: Optional explicit budget
            data_volume_tb: Optional explicit data volume
            query_rate_qps: Optional explicit query rate

        Returns:
            Parsed Requirements object
        """
        logger.info(f"Parsing requirements from: {description[:100]}...")

        # Parse workload type from description
        workload_type = self._detect_workload_type(description)

        # Parse traffic profile
        traffic_profile = self._detect_traffic_profile(description, query_rate_qps)

        # Parse availability requirement
        availability = self._detect_availability_requirement(description)

        # Parse data volume (in TB)
        volume_tb = self._detect_data_volume(description, data_volume_tb)

        # Parse query rate (QPS)
        qps = self._detect_query_rate(description, query_rate_qps)

        # Parse budget
        budget = self._detect_budget(description, budget_monthly)

        # Determine retention days
        retention = self._detect_retention_days(description)

        # Determine constraints
        constraints = self._infer_constraints(description)

        requirements = Requirements(
            workload_type=workload_type,
            traffic_profile=traffic_profile,
            availability_requirement=availability,
            data_volume_tb=volume_tb,
            retention_days=retention,
            query_rate_qps=qps,
            budget_monthly=budget,
            constraints=constraints,
            raw_description=description
        )

        logger.info(f"Parsed requirements: {workload_type.value}, {traffic_profile.value}, "
                   f"{availability.value}, {volume_tb}TB, {qps} QPS, ${budget}/mo")

        return requirements

    def _detect_workload_type(self, description: str) -> WorkloadType:
        """Detect workload type from description"""
        desc_lower = description.lower()

        # Keyword patterns for each workload type
        patterns = {
            WorkloadType.REALTIME_ANALYTICS: [
                "real-time", "realtime", "analytics", "dashboard", "visualization",
                "streaming", "live", "metric", "monitoring"
            ],
            WorkloadType.TIME_SERIES: [
                "time series", "timeseries", "metrics", "monitoring", "iot",
                "sensor", "temporal", "historical data"
            ],
            WorkloadType.CLICKSTREAM: [
                "clickstream", "click", "web analytics", "user behavior",
                "pageview", "session", "traffic"
            ],
            WorkloadType.MICROSERVICES: [
                "microservice", "micro-service", "api", "rest", "graphql",
                "service-oriented", "soa"
            ],
            WorkloadType.BATCH_PROCESSING: [
                "batch", "etl", "data pipeline", "reporting", "warehouse",
                "offline", "scheduled"
            ],
            WorkloadType.WEB_APPLICATION: [
                "web", "website", "web application", "webapp", "cms",
                "ecommerce", "blog"
            ]
        }

        # Score each pattern
        scores = {}
        for workload, keywords in patterns.items():
            score = sum(1 for keyword in keywords if keyword in desc_lower)
            if score > 0:
                scores[workload] = score

        # Return highest score or default
        if scores:
            return max(scores.keys(), key=lambda k: scores[k])
        return WorkloadType.REALTIME_ANALYTICS  # Default for ClickHouse

    def _detect_traffic_profile(
        self,
        description: str,
        explicit_qps: Optional[int] = None
    ) -> TrafficProfile:
        """Detect traffic profile from description"""
        if explicit_qps:
            if explicit_qps < 100:
                return TrafficProfile.LOW
            elif explicit_qps < 1000:
                return TrafficProfile.MEDIUM
            elif explicit_qps < 10000:
                return TrafficProfile.HIGH
            else:
                return TrafficProfile.EXTREME

        desc_lower = description.lower()

        # Keyword-based detection
        if any(word in desc_lower for word in ["extreme", "very high", "massive"]):
            return TrafficProfile.EXTREME
        elif any(word in desc_lower for word in ["high", "heavy", "intense"]):
            return TrafficProfile.HIGH
        elif any(word in desc_lower for word in ["medium", "moderate", "normal"]):
            return TrafficProfile.MEDIUM
        else:
            return TrafficProfile.LOW

    def _detect_availability_requirement(self, description: str) -> AvailabilityRequirement:
        """Detect availability requirement from description"""
        desc_lower = description.lower()

        # Keyword-based detection
        if any(word in desc_lower for word in ["extreme", "mission critical", "five nines"]):
            return AvailabilityRequirement.EXTREME
        elif any(word in desc_lower for word in ["critical", "production", "sla"]):
            return AvailabilityRequirement.CRITICAL
        elif any(word in desc_lower for word in ["high", "ha", "reliable"]):
            return AvailabilityRequirement.HIGH
        else:
            return AvailabilityRequirement.STANDARD

    def _detect_data_volume(
        self,
        description: str,
        explicit_tb: Optional[float] = None
    ) -> float:
        """Detect data volume from description"""
        if explicit_tb:
            return explicit_tb

        # Look for patterns like "10 TB", "5TB", "1 terabyte"
        patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:TB|terabytes?|terabyte)',
            r'(\d+(?:\.\d+)?)\s*(?:TB)',
        ]

        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                return float(match.group(1))

        # Look for GB and convert
        gb_pattern = r'(\d+(?:\.\d+)?)\s*(?:GB|gigabytes?|gigabyte)'
        match = re.search(gb_pattern, description, re.IGNORECASE)
        if match:
            return float(match.group(1)) / 1024  # Convert GB to TB

        # Default volume
        return 1.0

    def _detect_query_rate(
        self,
        description: str,
        explicit_qps: Optional[int] = None
    ) -> int:
        """Detect query rate from description"""
        if explicit_qps:
            return explicit_qps

        # Look for patterns like "1000 QPS", "500 queries per second"
        patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:QPS|queries?\s+per\s+second)',
            r'(\d+(?:\.\d+)?)\s*(?:QPS)',
        ]

        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                return int(float(match.group(1)))

        # Estimate based on traffic profile
        if any(word in description.lower() for word in ["extreme", "massive"]):
            return 10000
        elif any(word in description.lower() for word in ["high", "heavy"]):
            return 5000
        elif any(word in description.lower() for word in ["medium", "moderate"]):
            return 500
        else:
            return 100

    def _detect_budget(
        self,
        description: str,
        explicit_budget: Optional[float] = None
    ) -> float:
        """Detect budget from description"""
        if explicit_budget:
            return explicit_budget

        # Look for patterns like "$500/month", "$1000 per month", "500 USD monthly"
        patterns = [
            r'\$(\d+(?:\.\d+)?)\s*(?:/?month|per\s+month|monthly)',
            r'(\d+(?:\.\d+)?)\s*(?:USD|dollars?)\s*(?:/?month|per\s+month|monthly)',
        ]

        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                return float(match.group(1))

        # Default budget
        return 500.0

    def _detect_retention_days(self, description: str) -> int:
        """Detect data retention period"""
        patterns = [
            r'(\d+)\s*(?:days?|day retention)',
            r'retention\s*:\s*(\d+)\s*days?',
        ]

        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                return int(match.group(1))

        # Default retention
        return self.DEFAULT_RETENTION_DAYS

    def _infer_constraints(self, description: str) -> InfrastructureConstraints:
        """Infer constraints from description"""
        constraints = InfrastructureConstraints()

        # Infer max droplets from availability
        if any(word in description.lower() for word in ["critical", "extreme"]):
            constraints.max_droplets = 20
        elif any(word in description.lower() for word in ["high", "ha"]):
            constraints.max_droplets = 15

        # Infer budget constraint per hour
        budget = self._detect_budget(description)
        constraints.max_cost_per_hour = budget / (30 * 24)

        return constraints

    def generate_design(self, requirements: Requirements) -> DesignSolution:
        """
        Generate optimal infrastructure design for given requirements.

        Args:
            requirements: Parsed infrastructure requirements

        Returns:
            Optimized DesignSolution
        """
        logger.info(f"Generating design for requirements: {requirements.workload_type.value}")

        # Validate requirements
        validation_errors = self._validate_requirements(requirements)
        if validation_errors:
            raise ValueError(f"Invalid requirements: {', '.join(validation_errors)}")

        # Generate component specifications
        clickhouse_cluster = self._design_clickhouse_cluster(requirements)
        kubernetes_cluster = self._design_kubernetes_cluster(requirements)
        monitoring = self._design_monitoring(requirements)

        # Estimate costs
        estimated_cost = self._estimate_cost(
            clickhouse_cluster,
            kubernetes_cluster,
            monitoring
        )

        # Estimate availability
        estimated_availability = self._estimate_availability(
            requirements.availability_requirement,
            clickhouse_cluster,
            kubernetes_cluster
        )

        # Check if solution meets requirements
        notes, warnings = self._analyze_solution(
            requirements,
            clickhouse_cluster,
            kubernetes_cluster,
            estimated_cost,
            estimated_availability
        )

        design = DesignSolution(
            design_id=f"design_{hash(requirements.raw_description) % 1000000}",
            requirements=requirements,
            clickhouse_cluster=clickhouse_cluster,
            kubernetes_cluster=kubernetes_cluster,
            monitoring=monitoring,
            estimated_monthly_cost=estimated_cost,
            estimated_availability=estimated_availability,
            deployment_time_hours=2.0,  # Base deployment time
            notes=notes,
            warnings=warnings
        )

        # Cache the design
        self.design_cache[design.design_id] = design

        logger.info(f"Generated design {design.design_id}: ${estimated_cost:.2f}/mo, "
                   f"{estimated_availability*100:.2f}% availability")

        return design

    def _validate_requirements(self, requirements: Requirements) -> List[str]:
        """Validate requirements"""
        errors = []

        if requirements.budget_monthly < self.MIN_BUDGET:
            errors.append(f"Budget too low: ${requirements.budget_monthly} (minimum ${self.MIN_BUDGET})")

        if requirements.data_volume_tb < 0:
            errors.append("Data volume must be positive")

        if requirements.query_rate_qps < 1:
            errors.append("Query rate must be at least 1 QPS")

        if len(requirements.constraints.providers) == 0:
            errors.append("At least one provider must be specified")

        return errors

    def _design_clickhouse_cluster(self, requirements: Requirements) -> ClickHouseClusterSpec:
        """Design ClickHouse cluster based on requirements"""
        # Determine cluster type
        cluster_type = "replicated"

        # Calculate shard count based on data volume
        # Each shard can handle ~5 TB
        shard_count = max(2, int(requirements.data_volume_tb / self.SHARD_SIZE_TB))
        shard_count = min(shard_count, 10)  # Cap at 10 shards

        # Determine replica count based on availability
        if requirements.availability_requirement in [AvailabilityRequirement.CRITICAL, AvailabilityRequirement.EXTREME]:
            replica_count = 3
        elif requirements.availability_requirement == AvailabilityRequirement.HIGH:
            replica_count = 2
        else:
            replica_count = 1

        # ZooKeeper nodes (need odd number for quorum)
        zookeeper_nodes = max(3, shard_count)
        if zookeeper_nodes % 2 == 0:
            zookeeper_nodes += 1

        # Calculate storage per node
        storage_per_node = max(100, int(requirements.data_volume_tb * 1024 / (shard_count * replica_count)))
        if storage_per_node > 2000:
            storage_per_node = 2000  # Cap at 2TB per node

        # Determine memory (256GB per TB of data)
        total_memory_gb = int(requirements.data_volume_tb * 256)
        total_memory = f"{total_memory_gb}Gi"

        # Determine CPU (4 cores per TB of data)
        total_cpu_cores = max(8, int(requirements.data_volume_tb * 4))
        total_cpu = f"{total_cpu_cores} cores"

        # Determine storage tier based on workload
        if requirements.workload_type in [WorkloadType.TIME_SERIES, WorkloadType.REALTIME_ANALYTICS]:
            storage_tier = StorageTier.NVME
        elif requirements.workload_type == WorkloadType.CLICKSTREAM:
            storage_tier = StorageTier.SSD
        else:
            storage_tier = StorageTier.SSD

        spec = ClickHouseClusterSpec(
            cluster_type=cluster_type,
            shard_count=shard_count,
            replica_count=replica_count,
            zookeeper_nodes=zookeeper_nodes,
            total_memory=total_memory,
            total_cpu=total_cpu,
            storage_per_node=f"{storage_per_node}GB",
            storage_tier=storage_tier
        )

        logger.info(f"Designed ClickHouse cluster: {shard_count} shards x {replica_count} replicas, "
                   f"{total_cpu}, {total_memory}, {storage_per_node}GB per node")

        return spec

    def _design_kubernetes_cluster(self, requirements: Requirements) -> KubernetesClusterSpec:
        """Design Kubernetes cluster based on requirements"""
        # Node count based on workload and availability
        if requirements.availability_requirement in [AvailabilityRequirement.CRITICAL, AvailabilityRequirement.EXTREME]:
            node_count = max(6, int(requirements.data_volume_tb * 2))
        elif requirements.availability_requirement == AvailabilityRequirement.HIGH:
            node_count = max(4, int(requirements.data_volume_tb * 1.5))
        else:
            node_count = max(3, int(requirements.data_volume_tb))

        # Cap node count
        node_count = min(node_count, requirements.constraints.max_droplets)

        # Calculate CPU (6 cores per node)
        total_cpu_cores = node_count * 6
        total_cpu = f"{total_cpu_cores} cores"

        # Calculate memory (32GB per node)
        total_memory_gb = node_count * 32
        total_memory = f"{total_memory_gb}Gi"

        # Enable HPA based on traffic profile
        enable_hpa = requirements.traffic_profile in [TrafficProfile.HIGH, TrafficProfile.EXTREME]

        # Enable PDB for critical availability
        enable_pdb = requirements.availability_requirement in [AvailabilityRequirement.CRITICAL, AvailabilityRequirement.EXTREME]

        spec = KubernetesClusterSpec(
            node_count=node_count,
            total_cpu=total_cpu,
            total_memory=total_memory,
            enable_hpa=enable_hpa,
            enable_pdb=enable_pdb
        )

        logger.info(f"Designed Kubernetes cluster: {node_count} nodes, "
                   f"{total_cpu}, {total_memory}, HPA={enable_hpa}")

        return spec

    def _design_monitoring(self, requirements: Requirements) -> MonitoringSpec:
        """Design monitoring stack"""
        # Enable full monitoring for production
        prometheus = True
        grafana = True
        alertmanager = True
        log_aggregation = True

        # Retention based on data retention
        retention_days = min(requirements.retention_days, 90)  # Cap at 90 days

        spec = MonitoringSpec(
            prometheus=prometheus,
            grafana=grafana,
            alertmanager=alertmanager,
            log_aggregation=log_aggregation,
            retention_days=retention_days
        )

        return spec

    def _estimate_cost(
        self,
        clickhouse: ClickHouseClusterSpec,
        kubernetes: KubernetesClusterSpec,
        monitoring: MonitoringSpec
    ) -> float:
        """Estimate monthly cost for the design"""
        hourly_cost = 0.0

        # ClickHouse cluster cost
        ch_cpu_cores = int(clickhouse.total_cpu.split()[0])
        ch_memory_gb = int(clickhouse.total_cpu.split()[0])
        ch_storage_gb = int(clickhouse.storage_per_node.replace("GB", ""))

        ch_hourly = (
            (ch_cpu_cores * self.COST_PER_CORE) +
            (ch_memory_gb * self.COST_PER_GB_RAM) +
            (ch_storage_gb * self.COST_PER_TB_SSD / 1000)
        )

        hourly_cost += ch_hourly

        # Kubernetes cluster cost
        k8s_cpu_cores = int(kubernetes.total_cpu.split()[0])
        k8s_memory_gb = int(kubernetes.total_memory.replace("Gi", ""))

        k8s_hourly = (
            (k8s_cpu_cores * self.COST_PER_CORE) +
            (k8s_memory_gb * self.COST_PER_GB_RAM)
        )

        hourly_cost += k8s_hourly

        # Monitoring cost (small overhead)
        monitoring_hourly = 0.05  # Small fixed cost for monitoring stack
        hourly_cost += monitoring_hourly

        # Convert to monthly (30 days * 24 hours)
        monthly_cost = hourly_cost * 30 * 24

        return round(monthly_cost, 2)

    def _estimate_availability(
        self,
        required: AvailabilityRequirement,
        clickhouse: ClickHouseClusterSpec,
        kubernetes: KubernetesClusterSpec
    ) -> float:
        """Estimate actual availability of the design"""
        # Base availability
        if required == AvailabilityRequirement.EXTREME:
            base = 0.9999  # 99.99%
        elif required == AvailabilityRequirement.CRITICAL:
            base = 0.9995  # 99.95%
        elif required == AvailabilityRequirement.HIGH:
            base = 0.999  # 99.9%
        else:
            base = 0.995  # 99.5%

        # Replication bonus
        if clickhouse.replica_count >= 3:
            base += 0.0003  # Extra reliability
        elif clickhouse.replica_count >= 2:
            base += 0.0001

        # Multi-shard bonus
        if clickhouse.shard_count >= 3:
            base += 0.0001

        # HPA bonus
        if kubernetes.enable_hpa:
            base += 0.0001

        # Cap at 99.99%
        availability = min(base, 0.9999)

        return availability

    def _analyze_solution(
        self,
        requirements: Requirements,
        clickhouse: ClickHouseClusterSpec,
        kubernetes: KubernetesClusterSpec,
        estimated_cost: float,
        estimated_availability: float
    ) -> Tuple[List[str], List[str]]:
        """Analyze the solution and generate notes and warnings"""
        notes = []
        warnings = []

        # Budget check
        if estimated_cost > requirements.budget_monthly:
            warnings.append(
                f"Estimated cost (${estimated_cost:.2f}/mo) exceeds budget "
                f"(${requirements.budget_monthly:.2f}/mo)"
            )
        else:
            utilization = (estimated_cost / requirements.budget_monthly) * 100
            notes.append(f"Budget utilization: {utilization:.1f}%")

        # Availability check
        required_avail = {
            AvailabilityRequirement.STANDARD: 0.995,
            AvailabilityRequirement.HIGH: 0.999,
            AvailabilityRequirement.CRITICAL: 0.9995,
            AvailabilityRequirement.EXTREME: 0.9999
        }[requirements.availability_requirement]

        if estimated_availability < required_avail:
            warnings.append(
                f"Estimated availability ({estimated_availability*100:.3f}%) "
                f"below requirement ({required_avail*100:.3f}%)"
            )
        else:
            notes.append(
                f"Availability target met: {estimated_availability*100:.3f}% "
                f"(required: {required_avail*100:.3f}%)"
            )

        # Scale warnings
        if kubernetes.node_count >= requirements.constraints.max_droplets:
            warnings.append(
                f"Node count ({kubernetes.node_count}) at max allowed "
                f"({requirements.constraints.max_droplets})"
            )

        # Performance notes
        if requirements.traffic_profile in [TrafficProfile.HIGH, TrafficProfile.EXTREME]:
            notes.append("High-performance configuration with NVMe storage for optimal query performance")

        if requirements.workload_type == WorkloadType.REALTIME_ANALYTICS:
            notes.append("Optimized for real-time analytics with low-latency queries")

        return notes, warnings


def create_design_engine() -> DesignEngine:
    """Factory function to create DesignEngine"""
    return DesignEngine()
