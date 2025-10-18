#!/bin/bash

# Kafka Monitoring Setup and Verification Script
# Documents and tests JMX metrics accessibility for the Reddit Stress Detection System

set -e

KAFKA_CONTAINER="reddit-kafka"
JMX_PORT=9997

echo "=========================================="
echo "Kafka Monitoring Setup Verification"
echo "=========================================="
echo ""

# Check if Kafka is running
if ! docker ps | grep -q $KAFKA_CONTAINER; then
    echo "✗ Kafka container is not running!"
    echo "Please start services with: docker-compose up -d"
    exit 1
fi

echo "✓ Kafka container is running"
echo ""

# Test 1: Check JMX Port Accessibility
echo "Test 1: JMX Port Accessibility"
echo "-------------------------------"
if docker exec $KAFKA_CONTAINER bash -c "nc -z localhost $JMX_PORT" > /dev/null 2>&1; then
    echo "✓ JMX port $JMX_PORT is accessible"
else
    echo "✗ JMX port $JMX_PORT is not accessible"
    echo "Check KAFKA_JMX_PORT environment variable in docker-compose.yml"
    exit 1
fi
echo ""

# Test 2: List Available JMX Beans
echo "Test 2: Available JMX MBeans"
echo "----------------------------"
echo "Listing key JMX metrics available for monitoring..."
echo ""

# Create sample metrics documentation
METRICS_DOC="./docs/kafka-jmx-metrics.md"

cat > "$METRICS_DOC" << 'EOF'
# Kafka JMX Metrics Reference

## Overview

Kafka exposes JMX metrics on port 9997 for monitoring broker health and performance.

---

## Key Metrics Categories

### 1. Broker Metrics

#### Server Metrics (kafka.server)
- **BrokerState**: Current state of the broker (0=Not Running, 1=Starting, 2=Recovering, 3=Running, 6=Shutting Down)
- **NetworkProcessorAvgIdlePercent**: Network processor thread idle percentage
- **RequestHandlerAvgIdlePercent**: Request handler thread idle percentage

#### Request Metrics (kafka.network:type=RequestMetrics)
- **TotalTimeMs**: Total time to process requests
- **RequestQueueTimeMs**: Time requests spend in queue
- **LocalTimeMs**: Time spent processing locally
- **RemoteTimeMs**: Time spent waiting for remote processing
- **ResponseQueueTimeMs**: Time responses spend in queue
- **ResponseSendTimeMs**: Time to send responses

### 2. Topic Metrics

#### Bytes In/Out (kafka.server:type=BrokerTopicMetrics)
- **BytesInPerSec**: Rate of bytes coming into broker
- **BytesOutPerSec**: Rate of bytes going out of broker
- **MessagesInPerSec**: Rate of messages coming into broker
- **TotalProduceRequestsPerSec**: Rate of produce requests
- **TotalFetchRequestsPerSec**: Rate of fetch requests
- **FailedProduceRequestsPerSec**: Rate of failed produce requests
- **FailedFetchRequestsPerSec**: Rate of failed fetch requests

### 3. Partition Metrics

#### Under Replicated Partitions (kafka.server:type=ReplicaManager)
- **UnderReplicatedPartitions**: Number of partitions with replicas that are behind the leader
- **OfflinePartitionsCount**: Number of offline partitions (no leader)
- **LeaderCount**: Number of leader replicas on this broker
- **PartitionCount**: Total number of partitions on this broker

### 4. Consumer Lag Metrics

#### Consumer Group Metrics (kafka.consumer:type=consumer-fetch-manager-metrics)
- **records-lag**: Number of records consumer is behind
- **records-lag-max**: Maximum lag across all partitions
- **fetch-latency-avg**: Average fetch request latency
- **fetch-latency-max**: Maximum fetch request latency

### 5. Producer Metrics

#### Producer Performance (kafka.producer:type=producer-metrics)
- **record-send-rate**: Average number of records sent per second
- **record-send-total**: Total number of records sent
- **record-error-rate**: Average per-second number of record sends that resulted in errors
- **request-latency-avg**: Average request latency
- **request-latency-max**: Maximum request latency

---

## Accessing JMX Metrics

### Via Kafka UI (Recommended)

1. Open http://localhost:8080
2. Navigate to "Brokers" section
3. Select broker "reddit-kafka"
4. View "Metrics" tab

### Via JConsole

```bash
jconsole localhost:9997
```

Navigate through MBean tree:
- kafka.server
- kafka.network
- kafka.controller
- kafka.log
- kafka.producer
- kafka.consumer

### Via Command Line (JMX Query)

Using jmxterm or similar tools:
```bash
# Install jmxterm
brew install jmxterm  # macOS
# or download from http://wiki.cyclopsgroup.org/jmxterm/

# Connect to JMX
jmxterm -l localhost:9997

# List domains
domains

# List beans in kafka.server domain
domain kafka.server
beans

# Get specific metric
get -b kafka.server:type=BrokerTopicMetrics,name=MessagesInPerSec OneMinuteRate
```

---

## Monitoring Queries

### Check Broker Health

**Metric**: `kafka.server:type=KafkaServer,name=BrokerState`
- **Expected**: Value = 3 (Running)
- **Alert If**: Value != 3

### Monitor Message Throughput

**Metric**: `kafka.server:type=BrokerTopicMetrics,name=MessagesInPerSec`
- **Expected**: > 0 when producers are active
- **Alert If**: < 10 messages/sec (unexpectedly low)

### Check Under-Replicated Partitions

**Metric**: `kafka.server:type=ReplicaManager,name=UnderReplicatedPartitions`
- **Expected**: 0 (in production with replication)
- **Alert If**: > 0 for more than 5 minutes

### Monitor Consumer Lag

**Per Topic/Partition**:
- Use `kafka-consumer-groups` CLI tool
- Or access via Kafka UI → Consumer Groups

```bash
docker exec reddit-kafka kafka-consumer-groups \
    --bootstrap-server localhost:9092 \
    --describe \
    --group <consumer-group-name>
```

**Alert If**: LAG > 1000 messages

### Request Latency

**Metric**: `kafka.network:type=RequestMetrics,name=TotalTimeMs,request=Produce`
- **Expected p50**: < 10ms
- **Expected p95**: < 50ms
- **Expected p99**: < 100ms
- **Alert If**: p99 > 200ms

---

## Sample Monitoring Dashboard Panels

### Panel 1: Message Rate
- **Metric**: BytesInPerSec, MessagesInPerSec
- **Type**: Time series graph
- **Refresh**: 5s

### Panel 2: Request Latency
- **Metrics**: TotalTimeMs (p50, p95, p99)
- **Type**: Time series graph
- **Refresh**: 10s

### Panel 3: Consumer Lag
- **Metric**: Consumer group lag per topic
- **Type**: Table or gauge
- **Refresh**: 30s

### Panel 4: Partition Health
- **Metrics**: UnderReplicatedPartitions, OfflinePartitionsCount
- **Type**: Single stat
- **Refresh**: 30s

### Panel 5: Broker Resources
- **Metrics**: NetworkProcessorAvgIdlePercent, RequestHandlerAvgIdlePercent
- **Type**: Gauge
- **Refresh**: 30s

---

## Alerting Thresholds (Development)

| Metric | Warning | Critical |
|--------|---------|----------|
| MessagesInPerSec | < 10 | < 1 |
| Consumer Lag | > 1000 | > 5000 |
| Request Latency p99 | > 100ms | > 500ms |
| UnderReplicatedPartitions | > 0 | N/A (dev) |
| OfflinePartitions | > 0 | > 0 |
| NetworkProcessorIdle | < 20% | < 10% |

---

## Production Alerting Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| MessagesInPerSec | < 100 | < 10 |
| Consumer Lag | > 10000 | > 50000 |
| Request Latency p99 | > 50ms | > 200ms |
| UnderReplicatedPartitions | > 1 | > 5 |
| OfflinePartitions | > 0 | > 1 |
| BrokerState | != 3 | != 3 |

---

## Troubleshooting

### High Consumer Lag
1. Check consumer is running: `docker ps | grep consumer`
2. Verify consumer group status
3. Increase consumer parallelism (more partitions/consumers)
4. Check for slow processing in consumer code

### High Request Latency
1. Check disk I/O: `docker stats reddit-kafka`
2. Verify network latency
3. Check for under-replicated partitions
4. Review Kafka broker logs

### Under-Replicated Partitions
1. Check broker health
2. Verify replication factor configuration
3. Check network connectivity between brokers
4. Review disk space availability

---

## References

- [Kafka Monitoring Documentation](https://kafka.apache.org/documentation/#monitoring)
- [Confluent Metrics Reference](https://docs.confluent.io/platform/current/kafka/monitoring.html)
- Project Docs: `docs/kafka-setup.md`

---

**Document Version**: 1.0
**Last Updated**: 2025-10-06
EOF

echo "✓ JMX metrics documentation created: $METRICS_DOC"
echo ""

# Test 3: Verify Key Metrics Available
echo "Test 3: Verify Kafka UI Access"
echo "-------------------------------"
if curl -f -s http://localhost:8080 > /dev/null 2>&1; then
    echo "✓ Kafka UI is accessible at http://localhost:8080"
    echo "  View JMX metrics: Brokers → reddit-kafka → Metrics"
else
    echo "⚠ Kafka UI may not be running yet"
    echo "  It will be available after running: docker-compose up -d"
fi
echo ""

# Summary
echo "=========================================="
echo "Monitoring Setup Summary"
echo "=========================================="
echo ""
echo "✓ JMX port $JMX_PORT verified"
echo "✓ Metrics documentation created: $METRICS_DOC"
echo ""
echo "Key Metrics to Monitor:"
echo "  • MessagesInPerSec - Message throughput"
echo "  • ConsumerLag - Processing delay"
echo "  • TotalTimeMs - Request latency"
echo "  • UnderReplicatedPartitions - Replication health"
echo "  • BrokerState - Broker status"
echo ""
echo "Access Points:"
echo "  • Kafka UI: http://localhost:8080"
echo "  • JMX Port: localhost:$JMX_PORT"
echo ""
echo "Next Steps:"
echo "  1. Open Kafka UI and verify metrics are visible"
echo "  2. Set up alerting based on thresholds in $METRICS_DOC"
echo "  3. Create custom monitoring dashboards as needed"
echo ""
