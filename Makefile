# VOZ Real-Time Stress Detection Pipeline
# Usage: make demo

.PHONY: all demo start stop clean infra producer consumer streamlit status logs help

# Configuration
ROOT_DIR := $(shell pwd)
VENV := source $(ROOT_DIR)/.venv/bin/activate &&
DOCKER_COMPOSE := docker-compose
TARGET_POSTS := 50
DELAY := 0.5

# ============================================================================
# Main Commands
# ============================================================================

help:
	@echo "VOZ Stress Detection Pipeline"
	@echo ""
	@echo "Quick Start:"
	@echo "  make demo          - Start complete pipeline (infra + all components)"
	@echo "  make stop          - Stop all components"
	@echo ""
	@echo "Individual Components:"
	@echo "  make infra         - Start Docker services (Kafka, Cassandra)"
	@echo "  make producer      - Start VOZ crawler → Kafka"
	@echo "  make consumer      - Start Kafka → LLM → Cassandra"
	@echo "  make streamlit     - Start dashboard at http://localhost:8501"
	@echo ""
	@echo "Utilities:"
	@echo "  make status        - Check all services status"
	@echo "  make logs          - Tail consumer logs"
	@echo "  make clean         - Stop everything and clean up"
	@echo "  make cassandra-shell - Open Cassandra CQL shell"
	@echo ""
	@echo "Pipeline: VOZ.vn → Kafka → LLM (llama3.1:8b) → Cassandra → Streamlit"

demo: infra wait-kafka init-schemas check-ollama consumer-bg producer-bg streamlit-bg status
	@echo ""
	@echo "=============================================="
	@echo "✓ Demo pipeline started!"
	@echo "=============================================="
	@echo ""
	@echo "Access:"
	@echo "  Dashboard:  http://localhost:8501"
	@echo "  Kafka UI:   http://localhost:8080"
	@echo ""
	@echo "To stop: make stop"

# ============================================================================
# Infrastructure
# ============================================================================

infra:
	@echo "Starting Docker services..."
	$(DOCKER_COMPOSE) up -d zookeeper kafka cassandra kafka-ui
	@echo "✓ Docker services started"

wait-kafka:
	@echo "Waiting for Kafka to be re ady..."
	@sleep 10
	@until docker exec reddit-kafka kafka-broker-api-versions --bootstrap-server localhost:9092 2>/dev/null; do \
		echo "  Waiting for Kafka..."; \
		sleep 5; \
	done
	@echo "✓ Kafka is ready"

init-schemas:
	@echo "Initializing Kafka topics..."
	@./scripts/init-kafka-topics.sh 2>/dev/null || true
	@echo "Initializing Cassandra schemas..."
	@for schema in cassandra/schema/*.cql; do \
		docker exec -i reddit-cassandra cqlsh < "$$schema" 2>/dev/null || true; \
	done
	@echo "✓ Schemas initialized"

check-ollama:
	@echo "Checking Ollama..."
	@if curl -s http://localhost:11434/api/tags | grep -q "llama3.1:8b"; then \
		echo "✓ llama3.1:8b model ready"; \
	else \
		echo "⚠ llama3.1:8b not found. Run: ollama pull llama3.1:8b"; \
		exit 1; \
	fi

# ============================================================================
# Pipeline Components
# ============================================================================

producer:
	@echo "Starting VOZ producer (target: $(TARGET_POSTS) posts)..."
	$(VENV) python producers/voz_kafka_producer.py --target $(TARGET_POSTS) --delay $(DELAY)

producer-bg:
	@echo "Starting VOZ producer in background (continuous mode)..."
	@nohup bash -c '$(VENV) python producers/voz_kafka_producer.py --continuous --delay $(DELAY)' > /tmp/voz_producer.log 2>&1 &
	@echo $$! > /tmp/voz_producer.pid
	@sleep 1
	@echo "✓ Producer started (PID: $$(cat /tmp/voz_producer.pid)) - runs until stopped"

consumer:
	@echo "Starting LLM consumer..."
	$(VENV) python consumers/voz_llm_consumer.py

consumer-bg:
	@echo "Starting LLM consumer in background (continuous mode)..."
	@nohup bash -c '$(VENV) python consumers/voz_llm_consumer.py' > /tmp/voz_consumer.log 2>&1 &
	@echo $$! > /tmp/voz_consumer.pid
	@sleep 1
	@echo "✓ Consumer started (PID: $$(cat /tmp/voz_consumer.pid)) - runs until stopped"

streamlit:
	@echo "Starting Streamlit dashboard..."
	cd streamlit_app && $(VENV) streamlit run app.py --server.port 8501

streamlit-bg:
	@echo "Starting Streamlit in background..."
	@nohup bash -c 'cd streamlit_app && $(VENV) streamlit run app.py --server.port 8501 --server.headless true' > /tmp/streamlit.log 2>&1 &
	@echo $$! > /tmp/streamlit.pid
	@sleep 3
	@echo "✓ Streamlit started at http://localhost:8501"

# ============================================================================
# Control
# ============================================================================

stop:
	@echo "Stopping pipeline components..."
	@if [ -f /tmp/voz_producer.pid ]; then kill $$(cat /tmp/voz_producer.pid) 2>/dev/null || true; rm /tmp/voz_producer.pid; fi
	@if [ -f /tmp/voz_consumer.pid ]; then kill $$(cat /tmp/voz_consumer.pid) 2>/dev/null || true; rm /tmp/voz_consumer.pid; fi
	@if [ -f /tmp/streamlit.pid ]; then kill $$(cat /tmp/streamlit.pid) 2>/dev/null || true; rm /tmp/streamlit.pid; fi
	@pkill -f "voz_kafka_producer" 2>/dev/null || true
	@pkill -f "voz_llm_consumer" 2>/dev/null || true
	@pkill -f "streamlit run" 2>/dev/null || true
	@echo "✓ All components stopped"

stop-infra:
	@echo "Stopping Docker services..."
	$(DOCKER_COMPOSE) down
	@echo "✓ Docker services stopped"

clean: stop stop-infra
	@rm -f /tmp/voz_*.log /tmp/voz_*.pid /tmp/streamlit.*
	@echo "✓ Cleaned up"

# ============================================================================
# Utilities
# ============================================================================

status:
	@echo ""
	@echo "=============================================="
	@echo "Pipeline Status"
	@echo "=============================================="
	@echo ""
	@echo "Docker Services:"
	@docker ps --format "  {{.Names}}: {{.Status}}" 2>/dev/null | grep -E "(kafka|cassandra)" || echo "  Not running"
	@echo ""
	@echo "Python Components:"
	@if pgrep -f "voz_kafka_producer" > /dev/null; then echo "  Producer: ✓ Running"; else echo "  Producer: ✗ Stopped"; fi
	@if pgrep -f "voz_llm_consumer" > /dev/null; then echo "  Consumer: ✓ Running"; else echo "  Consumer: ✗ Stopped"; fi
	@if pgrep -f "streamlit" > /dev/null; then echo "  Streamlit: ✓ Running (http://localhost:8501)"; else echo "  Streamlit: ✗ Stopped"; fi
	@echo ""
	@echo "Ollama:"
	@if curl -s http://localhost:11434/api/tags 2>/dev/null | grep -q "llama3.1:8b"; then echo "  ✓ llama3.1:8b ready"; else echo "  ✗ Not available"; fi
	@echo ""
	@echo "Cassandra Data:"
	@docker exec reddit-cassandra cqlsh -e "SELECT COUNT(*) FROM reddit_rt.voz_classified_posts;" 2>/dev/null | grep -E "^\s*[0-9]+" | awk '{print "  Classified posts: " $$1}' || echo "  No data"
	@echo ""

logs:
	@echo "Consumer logs (Ctrl+C to exit):"
	@tail -f /tmp/voz_consumer.log 2>/dev/null || echo "No consumer logs found. Run: make consumer-bg"

logs-producer:
	@tail -f /tmp/voz_producer.log 2>/dev/null || echo "No producer logs found"

cassandra-shell:
	docker exec -it reddit-cassandra cqlsh

kafka-ui:
	@echo "Opening Kafka UI..."
	@open http://localhost:8080 2>/dev/null || echo "Visit: http://localhost:8080"

# ============================================================================
# Development
# ============================================================================

crawl:
	@echo "Crawling $(TARGET_POSTS) posts..."
	$(VENV) python producers/voz_kafka_producer.py --target $(TARGET_POSTS) --delay $(DELAY)

test-llm:
	@echo "Testing LLM inference..."
	$(VENV) python -c "from spark.llm_inference import LLMStressInference; llm = LLMStressInference(); print(llm.predict('Tôi rất căng thẳng với công việc'))"

reset-checkpoint:
	@rm -f data/raw/.voz_checkpoint.json data/raw/.voz_kafka_checkpoint.json
	@echo "✓ Checkpoint reset"

reset-cassandra:
	@docker exec reddit-cassandra cqlsh -e "TRUNCATE reddit_rt.voz_classified_posts;" 2>/dev/null
	@echo "✓ Cassandra data cleared"
