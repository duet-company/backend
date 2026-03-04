# AI Data Labs - On-Call Runbook

This runbook provides step-by-step procedures for handling common incidents.

## Incident Severity Levels

- **P0 - Critical**: System down, data loss, security breach
- **P1 - High**: Major functionality degraded, significant user impact
- **P2 - Medium**: Minor functionality degraded, limited user impact
- **P3 - Low**: Cosmetic issues, no user impact

## Incident Response Flow

1. **Detection**: Alert received from monitoring system
2. **Acknowledgment**: Acknowledge alert in incident management tool
3. **Assessment**: Determine severity and impact
4. **Containment**: Take immediate action to limit impact
5. **Resolution**: Fix the root cause
6. **Recovery**: Restore full functionality
7. **Post-Incident**: Document and learn from incident

## Common Incidents

### API Service Down

**Severity**: P0

**Detection**:
- Alert: APIServiceDown
- User reports: "API is unreachable"

**Immediate Actions**:
1. Check if the service is running: `systemctl status ai-datalabs-api`
2. Check application logs: `tail -f /var/log/ai-datalabs/app.log`
3. Check if port is listening: `netstat -tlnp | grep 8000`

**Troubleshooting**:

#### Service not running
```bash
# Restart service
systemctl restart ai-datalabs-api

# Check if it started successfully
systemctl status ai-datalabs-api
```

#### Port not listening
```bash
# Check what's using the port
lsof -i :8000

# Kill process if needed
kill -9 <PID>

# Restart service
systemctl restart ai-datalabs-api
```

#### Application crash
1. Check error logs for exception
2. Check memory/disk usage
3. If OOM (Out of Memory):
   - Increase memory allocation
   - Check for memory leaks
   - Add memory limit if needed

#### Database connection failed
1. Check PostgreSQL: `pg_isready -h localhost -p 5432`
2. Check ClickHouse: `clickhouse-client --query "SELECT 1"`
3. Restart database if needed

**Follow-up**:
- Document the root cause
- Update monitoring thresholds if needed
- Add automated recovery if possible

---

### High API Error Rate

**Severity**: P1

**Detection**:
- Alert: HighAPIErrorRate
- User reports: "Getting errors when using the API"

**Immediate Actions**:
1. Check error rate in Grafana dashboard
2. Check application logs for error patterns
3. Check if recent deployment caused the issue

**Troubleshooting**:

#### Recent deployment issue
```bash
# Check recent deployments
git log --oneline -10

# Rollback if needed
git revert <commit_hash>
systemctl restart ai-datalabs-api
```

#### Database errors
1. Check database logs
2. Check connection pool metrics
3. Restart database if needed
4. Scale database if overloaded

#### Agent errors
1. Check agent status: `curl http://localhost:8000/api/v1/monitoring/agents/status`
2. Restart specific agent if needed
3. Check LLM API status and quotas

#### Resource exhaustion
1. Check CPU, memory, disk usage
2. Scale up resources if needed
3. Implement rate limiting if overloaded

**Follow-up**:
- Identify the error root cause
- Fix the underlying issue
- Add automated tests to prevent recurrence

---

### Database Connection Pool Exhausted

**Severity**: P1

**Detection**:
- Alert: DatabasePoolExhausted
- User reports: "Database connection errors", "Slow queries"

**Immediate Actions**:
1. Check connection pool metrics in Grafana
2. Check active connections: `SELECT count(*) FROM pg_stat_activity;`
3. Check for long-running queries

**Troubleshooting**:

#### Long-running queries
```sql
-- Find long-running queries in PostgreSQL
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes'
ORDER BY duration DESC;

-- Kill a specific query
SELECT pg_terminate_backend(<pid>);
```

#### Connection leak
1. Check application code for connection leaks
2. Ensure connections are properly closed
3. Review connection pool configuration
4. Increase pool size temporarily if needed

#### Too many concurrent requests
1. Implement rate limiting
2. Scale up database
3. Add read replicas if needed
4. Optimize queries to reduce execution time

**Follow-up**:
- Review connection pool configuration
- Add connection monitoring
- Optimize slow queries
- Add circuit breakers if needed

---

### Agent Queue Backlog

**Severity**: P2

**Detection**:
- Alert: AgentQueueBacklog
- User reports: "Slow agent responses", "Tasks not completing"

**Immediate Actions**:
1. Check queue size metrics
2. Check agent status: `curl http://localhost:8000/api/v1/monitoring/agents/status`
3. Check agent logs

**Troubleshooting**:

#### Stuck agent
```bash
# Restart agent service
systemctl restart ai-datalabs-agent-<agent-name>

# Or restart all agents
systemctl restart ai-datalabs-api  # If agents are in same service
```

#### Slow agent execution
1. Check agent latency metrics
2. Check LLM API response times
3. Review agent logic for inefficiencies
4. Add caching if appropriate

#### Insufficient worker capacity
1. Scale up agent workers
2. Add more worker processes
3. Implement horizontal scaling

#### Queue corruption
1. Clear queue if corrupted (careful!)
2. Restart task queue system
3. Verify queue integrity

**Follow-up**:
- Add auto-restart for stuck agents
- Implement queue monitoring
- Add circuit breakers for failing agents
- Consider implementing dead letter queues

---

### Slow Query Execution

**Severity**: P2

**Detection**:
- Alert: SlowQueryExecution
- User reports: "Queries take too long"

**Immediate Actions**:
1. Check query performance metrics
2. Identify slow queries from logs
3. Check database performance

**Troubleshooting**:

#### ClickHouse slow queries
```sql
-- Find slow queries in ClickHouse
SELECT
    query,
    query_duration_ms,
    memory_usage
FROM system.query_log
WHERE type = 'QueryFinish'
  AND query_duration_ms > 5000
ORDER BY query_duration_ms DESC
LIMIT 10;
```

#### PostgreSQL slow queries
```sql
-- Enable slow query log if not already
ALTER SYSTEM SET log_min_duration_statement = 1000;
SELECT pg_reload_conf();

-- Find slow queries
SELECT
    query,
    mean_exec_time,
    calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

#### Missing indexes
1. Analyze query execution plan
2. Add appropriate indexes
3. Update statistics if needed
4. Rewrite queries if needed

#### Data volume
1. Consider data partitioning
2. Implement data archiving
3. Add more database nodes
4. Use materialized views for common queries

**Follow-up**:
- Add query performance monitoring
- Implement query optimization
- Add database maintenance tasks
- Consider implementing query timeouts

---

### High Memory Usage

**Severity**: P2

**Detection**:
- Alert: HighMemoryUsage
- System: OOM Killer entries in logs

**Immediate Actions**:
1. Check memory usage: `free -h`
2. Identify top memory consumers: `ps aux --sort=-%mem | head`
3. Check for memory leaks in logs

**Troubleshooting**:

#### Memory leak
1. Identify leaking process
2. Restart leaking service
3. Analyze heap dump if available
4. Fix the leak in code

#### Insufficient memory
1. Check instance size
2. Scale up memory allocation
3. Implement memory limits
4. Add memory swap if appropriate

#### Large data structures
1. Review code for large data structures
2. Implement streaming/processing in chunks
3. Add memory monitoring
4. Implement data pagination

**Follow-up**:
- Add memory profiling
- Implement memory limits
- Add automated restarts on OOM
- Review memory usage patterns

---

### High CPU Usage

**Severity**: P2

**Detection**:
- Alert: HighCPUUsage
- System: Slow response times

**Immediate Actions**:
1. Check CPU usage: `top` or `htop`
2. Identify top CPU consumers: `ps aux --sort=-%cpu | head`
3. Check for infinite loops in logs

**Troubleshooting**:

#### Infinite loop
1. Identify process with high CPU
2. Check process logs
3. Kill process if needed
4. Fix infinite loop in code

#### Insufficient CPU capacity
1. Check instance size
2. Scale up CPU allocation
3. Implement horizontal scaling
4. Add load balancing

#### Inefficient code
1. Profile the application
2. Identify performance bottlenecks
3. Optimize slow functions
4. Add caching where appropriate

#### Too many concurrent tasks
1. Limit concurrency
2. Implement task queues
3. Add rate limiting
4. Optimize task processing

**Follow-up**:
- Add CPU profiling
- Implement performance monitoring
- Add automated scaling
- Review code efficiency regularly

---

## Security Incidents

### Unauthorized Access Attempt

**Severity**: P0

**Detection**:
- Alert from authentication system
- Suspicious login attempts
- Unusual API access patterns

**Immediate Actions**:
1. Block suspicious IP addresses
2. Reset compromised credentials
3. Enable additional security controls
4. Document the incident

**Investigation**:
1. Review access logs
2. Identify affected accounts
3. Check for data exfiltration
4. Determine attack vector

**Containment**:
1. Isolate affected systems
2. Disable compromised accounts
3. Implement additional authentication
4. Notify security team

**Recovery**:
1. Restore from backups if needed
2. Patch vulnerabilities
3. Strengthen security controls
4. Train users on security

**Follow-up**:
- Conduct post-incident review
- Update security policies
- Implement additional monitoring
- Share lessons learned

---

## Post-Incident Process

### Incident Review Template

**Incident Summary**:
- Date and time
- Duration
- Severity level
- Systems affected

**Root Cause Analysis**:
- What happened?
- Why did it happen?
- What was the trigger?

**Impact Assessment**:
- Number of users affected
- Duration of outage
- Business impact

**Actions Taken**:
- What was done to resolve?
- Who was involved?
- Timeline of actions

**Prevention Measures**:
- What can be done to prevent recurrence?
- What monitoring needs to be added?
- What processes need to be updated?

### Follow-Up Actions

1. Update this runbook with lessons learned
2. Update monitoring/alerting thresholds
3. Add automation to prevent recurrence
4. Conduct training if needed
5. Update documentation

## Emergency Contacts

- **On-Call Engineer**: [Contact information]
- **Engineering Lead**: [Contact information]
- **Security Team**: [Contact information]
- **Management**: [Contact information]

## Escalation Path

1. **Level 1**: On-Call Engineer (0-30 minutes)
2. **Level 2**: Engineering Lead (30+ minutes, P0/P1)
3. **Level 3**: CTO/Management (1+ hour, P0 only)

## Additional Resources

- [Monitoring Setup](./MONITORING_SETUP.md)
- [API Documentation](../README.md)
- [Runbook Templates](https://github.com/GoogleCloudPlatform/prod-fix-samples)
- [Incident Response](https://sre.google/sre-book/incident-management/)
