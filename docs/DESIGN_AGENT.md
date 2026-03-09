# Platform Designer Agent - Documentation

Version: 1.0.0
Status: Full Implementation

## Overview

The Platform Designer Agent is an autonomous AI agent that designs, plans, and provisions scalable data platforms using Kubernetes and ClickHouse. It translates high-level business requirements into production-ready infrastructure designs, complete with cost estimates, availability projections, and Kubernetes manifests.

## Key Features

- **Natural Language Requirement Parsing**: Understand plain English descriptions of infrastructure needs
- **Intelligent Design Engine**: Multi-objective optimization balancing cost, performance, and availability
- **Kubernetes Manifest Generation**: Automatically generate YAML manifests for ClickHouse clusters, ZooKeeper, and monitoring stack
- **Cost Estimation**: Accurate cost predictions for infrastructure deployment
- **Availability Planning**: Calculate expected availability based on redundancy and configuration
- **Configuration Recommendations**: Provide tiered options (Standard, Performance, High-Availability)
- **Infrastructure-as-Code**: All designs exportable as Kubernetes manifests

## Quick Start

```python
from app.agents.design_agent import create_design_agent

# Create agent instance
agent = create_design_agent()

# Initialize agent (call in async context)
await agent._on_initialize()
```

## Usage Examples

### Parse Requirements

```python
result = await agent._parse_requirements({
    "description": "I need a real-time analytics platform with 10TB of data, handling about 1000 queries per second, with high availability. My budget is $1000 per month."
})

print(result["result"])
# {
#   "workload_type": "realtime_analytics",
#   "data_volume_tb": 10.0,
#   "query_rate_qps": 1000,
#   "availability_requirement": "high",
#   "budget_monthly": 1000.0,
#   ...
# }
```

### Design Platform

```python
result = await agent._design_platform({
    "description": "Real-time analytics with 10TB data, 1000 QPS, high availability, $1000 budget"
})

print(result["result"]["design_id"])
print(f"Cost: ${result['result']['estimated_monthly_cost']:.2f}/mo")
print(f"Availability: {result['result']['estimated_availability']*100:.3f}%")
```

### Generate Kubernetes Manifests

```python
# First create a design
design_result = await agent._design_platform({...})
design_id = design_result["result"]["design_id"]

# Generate manifests
manifests_result = await agent._generate_manifests({
    "design_id": design_id
})

manifests = manifests_result["result"]["manifests"]
for manifest in manifests:
    print(f"--- {manifest['type']}: {manifest['name']} ---")
    print(manifest["yaml"])
```

### Estimate Cost

```python
cost_result = await agent._estimate_cost({
    "description": "Analytics platform with 5TB data",
    "budget_monthly": 500.0
})

print(f"Estimated monthly cost: ${cost_result['result']['total_monthly_cost']:.2f}")
```

### Get Configuration Recommendations

```python
rec_result = await agent._recommend_configuration({
    "description": "Analytics platform with 10TB data",
    "budget_monthly": 1000.0
})

for rec in rec_result["result"]["recommendations"]:
    print(f"{rec['tier']}: ${rec['cost_monthly']:.2f}/mo, {rec['availability']*100:.3f}% availability")
```

## Agent Actions

The Platform Designer Agent supports the following actions:

| Action | Description | Required Parameters |
|--------|-------------|---------------------|
| `parse_requirements` | Parse natural language description into structured requirements | `description` |
| `design_platform` | Generate complete infrastructure design | `description` OR `requirements` |
| `generate_manifests` | Generate Kubernetes manifests for a design | `design_id` |
| `provision_cluster` | Create deployment plan (dry-run) | `design_id`, `cluster_name` |
| `estimate_cost` | Estimate infrastructure cost | `design_id` OR `description` |
| `recommend_configuration` | Get multiple configuration options | `description` |
| `get_design` | Retrieve a saved design by ID | `design_id` |
| `list_designs` | List all saved designs | optional: `limit` |

## Design Output Structure

A `DesignSolution` includes:

```python
{
  "design_id": "design_123456",
  "requirements": {
    "workload_type": "realtime_analytics",
    "traffic_profile": "medium",
    "availability_requirement": "high",
    "data_volume_tb": 10.0,
    "retention_days": 30,
    "query_rate_qps": 1000,
    "budget_monthly": 1000.0
  },
  "clickhouse_cluster": {
    "cluster_type": "replicated",
    "shard_count": 3,
    "replica_count": 2,
    "zookeeper_nodes": 3,
    "total_memory": "48Gi",
    "total_cpu": "12 cores",
    "storage_per_node": "1000GB",
    "storage_tier": "ssd"
  },
  "kubernetes_cluster": {
    "namespace": "aidatalabs",
    "node_count": 6,
    "total_cpu": "12 cores",
    "total_memory": "48Gi",
    "enable_hpa": True,
    "enable_pdb": False
  },
  "monitoring": {
    "prometheus": True,
    "grafana": True,
    "alertmanager": True,
    "log_aggregation": True,
    "retention_days": 30
  },
  "estimated_monthly_cost": 850.50,
  "estimated_availability": 0.9995,
  "deployment_time_hours": 2.0,
  "notes": [...],
  "warnings": [...]
}
```

## Supported Workload Types

- `realtime_analytics` - Real-time dashboards and metrics
- `time_series` - Time-series data (IoT, sensors)
- `clickstream` - Web analytics and user behavior
- `microservices` - API-first architectures
- `batch_processing` - ETL and data pipelines
- `web_application` - Traditional web apps

## Traffic Profiles

- `low` - < 100 QPS
- `medium` - 100 - 1000 QPS
- `high` - 1000 - 10000 QPS
- `extreme` - > 10000 QPS

## Availability Levels

- `standard` - 99.5% (3.65 days/year downtime)
- `high` - 99.9% (8.76 hours/year downtime)
- `critical` - 99.95% (4.38 hours/year downtime)
- `extreme` - 99.99% (52.56 minutes/year downtime)

## Generated Kubernetes Manifests

The agent generates the following manifests:

1. **Namespace** - `aidatalabs`
2. **ConfigMap** - ClickHouse configuration
3. **Service** - ClickHouse HTTP and TCP endpoints
4. **StatefulSet** - ClickHouse cluster
5. **Service** - ZooKeeper (if replicating)
6. **StatefulSet** - ZooKeeper ensemble (if replicating)
7. **Deployment** - Prometheus (if monitoring enabled)
8. **Service** - Prometheus
9. **Deployment** - Grafana (if monitoring enabled)
10. **Service** - Grafana
11. **Deployment** - AlertManager (if monitoring enabled)
12. **Service** - AlertManager

## Cost Estimation Model

Monthly cost is estimated based on:
- Compute: $0.05 per core-hour
- Memory: $0.01 per GB-hour
- Storage: $0.02 per TB-hour (SSD)

These are approximate cloud provider rates. Actual costs may vary by region and provider.

## Integration with Backend API

The Design Agent is registered with the agent framework and can be invoked via the API:

```bash
POST /api/v1/agents/design_agent/process
{
  "action": "design_platform",
  "parameters": {
    "description": "Real-time analytics with 5TB data, medium traffic, high availability, $800 budget"
  }
}
```

## Testing

The agent includes comprehensive unit tests in `tests/agents/test_design_agent.py`. Run with:

```bash
pytest tests/agents/test_design_agent.py -v
```

Test coverage includes:
- Requirement parsing
- Platform design generation
- Kubernetes manifest generation
- Cost estimation
- Configuration recommendations
- Deployment planning
- Error handling
- Integration workflows

## Design Engine Algorithm

The design engine uses a rule-based approach with multi-objective optimization:

1. **Shard Calculation**: Based on data volume (5TB per shard)
2. **Replica Determination**: Based on availability requirements
3. **Node Sizing**: Based on memory/CPU requirements
4. **Availability Scoring**: Adjusts base availability based on HA features
5. **Cost Calculation**: Aggregates compute, memory, and storage costs
6. **Constraint Validation**: Ensures design fits within budget and limits

## Future Enhancements

- Multi-cloud provider support (AWS, GCP, Azure)
- Advanced Kubernetes operators for ClickHouse management
- Terraform/Ansible generation for non-K8s deployments
- Automated deployment execution via K8s API
- Real-time cost tracking and alerts
- Self-healing infrastructure via AI Operations

## Architecture

```
Design Agent
├── DesignEngine (intelligent design logic)
├── K8sManifestGenerator (YAML generation)
├── State Management (designs, deployments)
└── API Layer (BaseAgent interface)
```

## Error Handling

The agent validates inputs and provides clear error messages:
- Missing required parameters
- Invalid workload types
- Budget too low for requirements
- Unsupported configurations
- Design not found errors

## Logging

Logs are emitted under the `agents.design_agent` namespace with:
- INFO: Design generation, parsing, deployments
- WARNING: Conformance warnings
- ERROR: Failures with stack traces

## Configuration

Default configuration (from `create_design_agent`):

```python
{
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
```

Environment variables:
- `KUBERNETES_API_SERVER` - Kubernetes API endpoint
- `KUBERNETES_NAMESPACE` - Default namespace

## Version History

- **1.0.0** (2026-03-09): Full implementation with design engine, manifest generation, and comprehensive testing

## References

- Issue #22: Platform Designer Agent - Full Implementation (Kanboard)
- Implementation Guide: docs/platform-designer-implementation.md
- Related Agents:
  - Query Agent (NL to SQL)
  - Support Agent (user assistance)
  - Monitoring (observability stack)

---

**Maintainer**: Duet Company AI Team
**License**: Proprietary
