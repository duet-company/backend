# AI Data Labs - Monitoring & Observability Setup

This document describes the monitoring and observability infrastructure for AI Data Labs.

## Overview

AI Data Labs uses a comprehensive monitoring stack consisting of:

- **Prometheus**: Metrics collection and storage
- **Grafana**: Visualization and dashboards
- **Alertmanager**: Alert routing and notification
- **Loki**: Log aggregation (optional)
- **Custom Metrics Module**: Application-level metrics instrumentation

## Architecture

```
Application → Prometheus Metrics (/metrics) → Prometheus → Grafana
                              ↓
                        Alertmanager → Notifications (Email, Slack, PagerDuty)
                              ↓
                           Loki ← Logs (JSON format)
```

## Metrics Defined

### API Metrics

- `ai_datalabs_api_requests_total`: Total API requests (labels: method, endpoint, status)
- `ai_datalabs_api_latency_seconds`: API request latency (labels: method, endpoint)
- `ai_datalabs_api_active_requests`: Currently active API requests (labels: endpoint)

### Agent Metrics

- `ai_datalabs_agent_executions_total`: Agent executions (labels: agent_name, task_type, status)
- `ai_datalabs_agent_latency_seconds`: Agent execution latency (labels: agent_name, task_type)
- `ai_datalabs_agent_active_tasks`: Active agent tasks (labels: agent_name)
- `ai_datalabs_agent_queue_size`: Agent queue size (labels: agent_name)

### LLM Metrics

- `ai_datalabs_llm_requests_total`: LLM API requests (labels: provider, model, status)
- `ai_datalabs_llm_tokens_total`: LLM tokens processed (labels: provider, model, type)
- `ai_datalabs_llm_latency_seconds`: LLM API latency (labels: provider, model)

### Database Metrics

- `ai_datalabs_db_queries_total`: Database queries (labels: db_type, operation, status)
- `ai_datalabs_db_query_latency_seconds`: Query latency (labels: db_type, operation)
- `ai_datalabs_db_connections_active`: Active database connections (labels: db_type)
- `ai_datalabs_db_connection_pool_size`: Connection pool size (labels: db_type)

### Query/Chat Metrics

- `ai_datalabs_query_executions_total`: Query executions (labels: status, query_type)
- `ai_datalabs_query_latency_seconds`: Query execution latency (labels: query_type)
- `ai_datalabs_chat_requests_total`: Chat requests (labels: status)
- `ai_datalabs_chat_latency_seconds`: Chat request latency

### System Metrics

- `ai_datalabs_system_memory_usage_bytes`: System memory usage
- `ai_datalabs_system_cpu_usage_percent`: CPU usage percentage

### Error Metrics

- `ai_datalabs_errors_total`: Total errors (labels: component, error_type, severity)

## Installation

### 1. Install Dependencies

```bash
pip install prometheus-client psutil python-json-logger
```

### 2. Configure Prometheus

Create `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'ai-datalabs-api'
    static_configs:
      - targets: ['localhost:9090']  # Metrics server port
        labels:
          app: 'ai-datalabs'
          environment: 'production'

rule_files:
  - 'prometheus-alerts.yml'

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']
```

### 3. Configure Alertmanager

Create `alertmanager.yml`:

```yaml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'severity']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default'

receivers:
  - name: 'default'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
        channel: '#alerts'
        send_resolved: true

    email_configs:
      - to: 'oncall@aidatalabs.ai'
        send_resolved: true

  - name: 'critical'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
        channel: '#critical-alerts'
        send_resolved: true

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'instance']
```

### 4. Setup Grafana

1. Add Prometheus as a data source
2. Import the dashboard from `grafana-dashboard.json`
3. Set up notification channels

### 5. Start Services

```bash
# Start Prometheus
prometheus --config.file=prometheus.yml

# Start Alertmanager
alertmanager --config.file=alertmanager.yml

# Start Grafana
grafana-server
```

## Usage

### Instrumenting Your Code

```python
from app.core.metrics import MetricsContext, AgentMetricsContext

# API endpoint
@app.get("/api/query")
async def query():
    with MetricsContext("GET", "/api/query"):
        # Your code here
        pass

# Agent execution
async def run_agent():
    with AgentMetricsContext("QueryAgent", "nl2sql"):
        # Your agent code here
        pass
```

### Recording Metrics

```python
from app.core.metrics import (
    record_llm_request, record_query_execution,
    update_db_connections, update_agent_queue
)

# Record LLM request
record_llm_request(
    provider="anthropic",
    model="claude-3-opus",
    status="success",
    prompt_tokens=1000,
    completion_tokens=500,
    latency=2.5
)

# Record query execution
record_query_execution(status="success", query_type="select", latency=1.2)

# Update database connections
update_db_connections(db_type="postgres", active=5, pool_size=10)

# Update agent queue
update_agent_queue(agent_name="QueryAgent", queue_size=25)
```

### Checking Health

```bash
# Health check
curl http://localhost:8000/health

# Readiness check
curl http://localhost:8000/health/ready

# Liveness check
curl http://localhost:8000/health/live

# Platform metrics
curl http://localhost:8000/api/v1/monitoring/metrics/platform

# Alerts
curl http://localhost:8000/api/v1/monitoring/alerts
```

## Alert Rules

Alerts are defined in `prometheus-alerts.yml`:

### Critical Alerts

- **API Service Down**: API service unreachable for >2 minutes
- **Database Pool Exhausted**: >90% of connection pool used
- **High Database Error Rate**: >1 error/second
- **Low Disk Space**: <10% free space on root filesystem

### Warning Alerts

- **High API Error Rate**: >0.1 errors/second
- **High API Latency**: P95 > 2 seconds
- **High Agent Error Rate**: >0.5 errors/second
- **Agent Queue Backlog**: >100 tasks in queue
- **Slow Agent Execution**: P95 > 60 seconds
- **Slow Database Queries**: P95 > 1 second
- **High CPU Usage**: >80% for 10 minutes
- **High Memory Usage**: >80% for 10 minutes
- **High Query Error Rate**: >0.1 errors/second

## On-Call Procedures

### 1. High API Error Rate

**Symptoms:**
- Alert: HighAPIErrorRate
- Users experiencing errors

**Investigation:**
1. Check Grafana dashboard for spike in errors
2. Check application logs for error patterns
3. Check if recent deployment caused the issue

**Resolution:**
- Identify root cause from logs
- Rollback if recent deployment
- Scale up if resource exhaustion
- Fix bug if identified

### 2. Database Pool Exhaustion

**Symptoms:**
- Alert: DatabasePoolExhausted
- Slow API responses
- Database connection errors

**Investigation:**
1. Check connection pool metrics
2. Check for long-running queries
3. Check for connection leaks

**Resolution:**
- Identify and kill long-running queries
- Increase pool size if needed
- Fix connection leaks in code
- Scale database if needed

### 3. Agent Queue Backlog

**Symptoms:**
- Alert: AgentQueueBacklog
- Slow agent responses
- Tasks not being processed

**Investigation:**
1. Check queue size metrics
2. Check agent health status
3. Check for stuck agents

**Resolution:**
- Restart stuck agents
- Scale up agent workers
- Clear queue if corrupted
- Investigate performance bottleneck

### 4. High CPU Usage

**Symptoms:**
- Alert: HighCPUUsage
- Slow response times
- System lag

**Investigation:**
1. Check CPU usage dashboard
2. Identify top CPU consumers
3. Check for runaway processes

**Resolution:**
- Scale up instance size
- Optimize resource-intensive code
- Limit concurrent tasks
- Implement rate limiting

## Troubleshooting

### Prometheus Not Scraping Metrics

```bash
# Check if metrics endpoint is accessible
curl http://localhost:9090/metrics

# Check Prometheus logs
journalctl -u prometheus

# Verify Prometheus config
promtool check config prometheus.yml
```

### Grafana Not Showing Data

1. Verify Prometheus datasource is configured correctly
2. Check Prometheus target status: http://localhost:9090/targets
3. Verify query syntax in Grafana panel
4. Check time range selection

### Alerts Not Firing

1. Check Alertmanager status: http://localhost:9093/#/status
2. Verify alert rules: http://localhost:9090/rules
3. Check alert evaluation logs
4. Verify notification channel configuration

### High Memory Usage

1. Check memory usage dashboard
2. Look for memory leaks in application logs
3. Review agent execution patterns
4. Check for data retention policies

## Best Practices

1. **Set meaningful labels**: Use consistent, hierarchical labels
2. **Monitor right things**: Focus on user-facing metrics first
3. **Set sensible thresholds**: Avoid alert fatigue with appropriate thresholds
4. **Review alerts regularly**: Adjust thresholds based on actual usage
5. **Document runbooks**: Keep on-call procedures up to date
6. **Test alerts**: Verify alert notification channels work
7. **Monitor your monitoring**: Ensure Prometheus/Alertmanager are healthy
8. **Use histograms for latency**: Better than averages for understanding distribution
9. **Track business metrics**: Not just technical metrics
10. **Keep metrics organized**: Use consistent naming conventions

## Additional Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Alertmanager Documentation](https://prometheus.io/docs/alerting/latest/alertmanager/)
- [Python Prometheus Client](https://github.com/prometheus/client_python)

## Support

For monitoring issues or questions:
- Check the troubleshooting section above
- Review application logs
- Contact the infrastructure team
- Create an issue on GitHub
