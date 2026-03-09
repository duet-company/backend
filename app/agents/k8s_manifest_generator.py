"""
Kubernetes Manifest Generator - Generate Kubernetes manifests for infrastructure deployment.

Simplified version for MVP - generates basic manifests for ClickHouse and monitoring.
"""

import logging
from typing import Dict, Any, List

from app.agents.design_engine import (
    ClickHouseClusterSpec,
    KubernetesClusterSpec,
    MonitoringSpec
)

logger = logging.getLogger("agents.k8s_manifest_generator")


class KubernetesManifestGenerator:
    """
    Generate Kubernetes manifests for platform infrastructure.

    Generates YAML manifests for:
    - Namespace
    - ClickHouse ConfigMap with basic configuration
    - ClickHouse Service + StatefulSet
    - Optional ZooKeeper for replicated clusters
    - Monitoring stack (Prometheus, Grafana, AlertManager)
    """

    def __init__(self):
        pass

    def generate_all_manifests(
        self,
        clickhouse_cluster: ClickHouseClusterSpec,
        kubernetes_cluster: KubernetesClusterSpec,
        monitoring: MonitoringSpec
    ) -> List[Dict[str, str]]:
        """
        Generate all Kubernetes manifests for the infrastructure.

        Args:
            clickhouse_cluster: ClickHouse cluster specification
            kubernetes_cluster: Kubernetes cluster specification
            monitoring: Monitoring specification

        Returns:
            List of manifests with metadata and YAML content
        """
        manifests = []

        # Namespace
        manifests.append(self._generate_namespace(kubernetes_cluster.namespace))

        # ClickHouse ConfigMap
        manifests.append(self._generate_clickhouse_configmap(clickhouse_cluster))

        # ZooKeeper if replicated
        if clickhouse_cluster.cluster_type == "replicated":
            manifests.append(self._generate_zookeeper_service())
            manifests.append(self._generate_zookeeper_statefulset(clickhouse_cluster))

        # ClickHouse Service and StatefulSet
        manifests.append(self._generate_clickhouse_service(clickhouse_cluster))
        manifests.append(self._generate_clickhouse_statefulset(clickhouse_cluster, kubernetes_cluster))

        # Monitoring
        if monitoring.prometheus:
            manifests.append(self._generate_prometheus_deployment())
            manifests.append(self._generate_prometheus_service())
        if monitoring.grafana:
            manifests.append(self._generate_grafana_deployment())
            manifests.append(self._generate_grafana_service())
        if monitoring.alertmanager:
            manifests.append(self._generate_alertmanager_deployment())
            manifests.append(self._generate_alertmanager_service())

        logger.info(f"Generated {len(manifests)} Kubernetes manifests")

        return manifests

    def _generate_namespace(self, namespace: str) -> Dict[str, str]:
        yaml = f"""---
apiVersion: v1
kind: Namespace
metadata:
  name: {namespace}
  labels:
    app: aidatalabs
"""
        return {"type": "Namespace", "name": namespace, "yaml": yaml}

    def _generate_clickhouse_configmap(self, spec: ClickHouseClusterSpec) -> Dict[str, str]:
        xml_config = """<clickhouse>
    <listen_host>0.0.0.0</listen_host>
    <http_port>8123</http_port>
    <tcp_port>9000</tcp_port>

    <logger>
        <level>information</level>
        <size>100M</size>
        <count>10</count>
    </logger>

    <users>
        <default>
            <password></password>
            <networks>
                <ip>::/0</ip>
            </networks>
            <profile>default</profile>
            <quota>default</quota>
        </default>
        <admin>
            <password>admin123</password>
            <networks>
                <ip>::/0</ip>
            </networks>
            <profile>default</profile>
            <quota>default</quota>
        </admin>
    </users>

    <profiles>
        <default>
            <max_memory_usage>10000000000</max_memory_usage>
            <use_uncompressed_cache>0</use_uncompressed_cache>
        </default>
    </profiles>
</clickhouse>"""

        yaml = f"""---
apiVersion: v1
kind: ConfigMap
metadata:
  name: clickhouse-config
  namespace: aidatalabs
data:
  config.xml: |
{self._indent(xml_config, 4)}
"""
        return {"type": "ConfigMap", "name": "clickhouse-config", "yaml": yaml}

    def _generate_zookeeper_service(self) -> Dict[str, str]:
        yaml = """---
apiVersion: v1
kind: Service
metadata:
  name: zookeeper
  namespace: aidatalabs
  labels:
    app: zookeeper
spec:
  ports:
  - port: 2181
    name: client
  clusterIP: None
  selector:
    app: zookeeper
"""
        return {"type": "Service", "name": "zookeeper-service", "yaml": yaml}

    def _generate_zookeeper_statefulset(self, spec: ClickHouseClusterSpec) -> Dict[str, str]:
        yaml = f"""---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: zookeeper
  namespace: aidatalabs
spec:
  serviceName: zookeeper
  replicas: {spec.zookeeper_nodes}
  selector:
    matchLabels:
      app: zookeeper
  template:
    metadata:
      labels:
        app: zookeeper
    spec:
      containers:
      - name: zookeeper
        image: zookeeper:3.8
        ports:
        - containerPort: 2181
        env:
        - name: ZOO_MY_ID
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        resources:
          requests:
            memory: "2Gi"
            cpu: "500m"
"""
        return {"type": "StatefulSet", "name": "zookeeper", "yaml": yaml}

    def _generate_clickhouse_service(self, spec: ClickHouseClusterSpec) -> Dict[str, str]:
        yaml = """---
apiVersion: v1
kind: Service
metadata:
  name: clickhouse
  namespace: aidatalabs
  labels:
    app: clickhouse
spec:
  ports:
  - port: 8123
    name: http
  - port: 9000
    name: tcp
  selector:
    app: clickhouse
"""
        return {"type": "Service", "name": "clickhouse-service", "yaml": yaml}

    def _generate_clickhouse_statefulset(self, spec: ClickHouseClusterSpec, k8s_spec: KubernetesClusterSpec) -> Dict[str, str]:
        replicas = spec.shard_count * spec.replica_count
        memory_gb = max(4, int(spec.total_memory.replace("Gi", "")) // max(1, replicas))
        cpu_m = max(1000, int(spec.total_cpu.split()[0]) // max(1, replicas))
        storage_gb = int(spec.storage_per_node.replace("GB", ""))

        yaml = f"""---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: clickhouse
  namespace: aidatalabs
spec:
  serviceName: clickhouse
  replicas: {replicas}
  selector:
    matchLabels:
      app: clickhouse
  template:
    metadata:
      labels:
        app: clickhouse
    spec:
      containers:
      - name: clickhouse
        image: clickhouse/clickhouse-server:latest
        ports:
        - containerPort: 8123
        - containerPort: 9000
        env:
        - name: CLICKHOUSE_DB
          value: default
        - name: CLICKHOUSE_USER
          value: default
        - name: CLICKHOUSE_PASSWORD
          value: ""
        resources:
          requests:
            memory: "{memory_gb // 2}Gi"
            cpu: "{cpu_m // 2}m"
          limits:
            memory: "{memory_gb}Gi"
            cpu: "{cpu_m}m"
        volumeMounts:
        - name: config
          mountPath: /etc/clickhouse-server
        - name: data
          mountPath: /var/lib/clickhouse
        livenessProbe:
          httpGet:
            path: /ping
            port: 8123
          initialDelaySeconds: 30
          periodSeconds: 10
      volumes:
      - name: config
        configMap:
          name: clickhouse-config
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: {storage_gb}Gi
"""
        return {"type": "StatefulSet", "name": "clickhouse", "yaml": yaml}

    def _generate_prometheus_deployment(self) -> Dict[str, str]:
        yaml = """---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
  namespace: aidatalabs
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      containers:
      - name: prometheus
        image: prom/prometheus:latest
        args:
          - '--config.file=/etc/prometheus/prometheus.yml'
          - '--storage.tsdb.path=/prometheus'
        ports:
        - containerPort: 9090
        resources:
          requests:
            memory: "4Gi"
            cpu: "2000m"
        volumeMounts:
        - name: config
          mountPath: /etc/prometheus
        - name: storage
          mountPath: /prometheus
      volumes:
      - name: config
        configMap:
          name: prometheus-config
      - name: storage
        emptyDir: {}
"""
        return {"type": "Deployment", "name": "prometheus", "yaml": yaml}

    def _generate_prometheus_service(self) -> Dict[str, str]:
        yaml = """---
apiVersion: v1
kind: Service
metadata:
  name: prometheus
  namespace: aidatalabs
spec:
  ports:
  - port: 9090
  selector:
    app: prometheus
"""
        return {"type": "Service", "name": "prometheus", "yaml": yaml}

    def _generate_grafana_deployment(self) -> Dict[str, str]:
        yaml = """---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: grafana
  namespace: aidatalabs
spec:
  replicas: 1
  selector:
    matchLabels:
      app: grafana
  template:
    metadata:
      labels:
        app: grafana
    spec:
      containers:
      - name: grafana
        image: grafana/grafana:latest
        ports:
        - containerPort: 3000
        env:
        - name: GF_SECURITY_ADMIN_PASSWORD
          value: "admin123"
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
        volumeMounts:
        - name: storage
          mountPath: /var/lib/grafana
      volumes:
      - name: storage
        emptyDir: {}
"""
        return {"type": "Deployment", "name": "grafana", "yaml": yaml}

    def _generate_grafana_service(self) -> Dict[str, str]:
        yaml = """---
apiVersion: v1
kind: Service
metadata:
  name: grafana
  namespace: aidatalabs
spec:
  ports:
  - port: 3000
  selector:
    app: grafana
"""
        return {"type": "Service", "name": "grafana", "yaml": yaml}

    def _generate_alertmanager_deployment(self) -> Dict[str, str]:
        yaml = """---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: alertmanager
  namespace: aidatalabs
spec:
  replicas: 1
  selector:
    matchLabels:
      app: alertmanager
  template:
    metadata:
      labels:
        app: alertmanager
    spec:
      containers:
      - name: alertmanager
        image: prom/alertmanager:latest
        ports:
        - containerPort: 9093
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
"""
        return {"type": "Deployment", "name": "alertmanager", "yaml": yaml}

    def _generate_alertmanager_service(self) -> Dict[str, str]:
        yaml = """---
apiVersion: v1
kind: Service
metadata:
  name: alertmanager
  namespace: aidatalabs
spec:
  ports:
  - port: 9093
  selector:
    app: alertmanager
"""
        return {"type": "Service", "name": "alertmanager", "yaml": yaml}

    def _indent(self, text: str, spaces: int) -> str:
        """Indent text by specified number of spaces"""
        indent = " " * spaces
        return "\n".join(indent + line if line.strip() else line for line in text.split("\n"))


def create_k8s_manifest_generator() -> KubernetesManifestGenerator:
    """Factory function to create KubernetesManifestGenerator"""
    return KubernetesManifestGenerator()
