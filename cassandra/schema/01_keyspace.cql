-- ============================================================================
-- Keyspace: reddit_rt
-- Description: Real-time Reddit stress detection analytics keyspace
-- Replication Strategy: NetworkTopologyStrategy for production-ready setup
-- ============================================================================

-- Create keyspace with NetworkTopologyStrategy
-- For development: dc1 replication factor = 1
-- For production: should be increased to 3+ for high availability
CREATE KEYSPACE IF NOT EXISTS reddit_rt
WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'dc1': 1
}
AND durable_writes = true;

-- Notes on Replication Strategy:
-- - NetworkTopologyStrategy: Recommended for production; datacenter-aware
-- - dc1: datacenter name (matches CASSANDRA_DC in docker-compose.yml)
-- - RF=1: Single replica for development (no redundancy)
-- - RF=3: Recommended for production (tolerates 1 node failure)
-- - durable_writes=true: Ensures commit log persistence (critical for data durability)
