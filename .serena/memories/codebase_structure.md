# Codebase Structure

```
doan/
├── producers/reddit_producer/    # Reddit data collection
│   ├── main.py                   # Entry point for producer
│   ├── reddit_stream.py          # Reddit streaming logic
│   ├── health_server.py          # Health check server
│   ├── config/config.yaml        # Producer configuration
│   └── utils/                    # Producer utilities
│
├── spark/                        # Spark streaming applications
│   ├── kafka_to_cassandra_with_absa.py  # Main ABSA pipeline
│   ├── kafka_to_cassandra_with_ml.py    # ML pipeline
│   ├── model_inference.py        # Binary stress model wrapper
│   ├── model_inference_absa.py   # Multi-label ABSA wrapper
│   └── apps/                     # Spark applications
│
├── ml/                           # Machine learning components
│   ├── models/                   # Model training and inference
│   │   ├── train_absa_phobert.py        # Multi-label ABSA training
│   │   ├── vietnamese_augmentation.py   # Text augmentation
│   │   ├── test_model.py                # Model testing utilities
│   │   └── vietnamese_absa_sentiment_phobert_v1/  # Trained model
│   ├── dataset/                  # Dataset preparation
│   │   └── label_vietnamese_with_ollama.py  # Automated labeling
│   └── lda/                      # LDA topic extraction
│       └── absa_mental_health_aspects.json  # ABSA aspects
│
├── cassandra/                    # Cassandra schemas
│   └── schema/                   # CQL schema files
│
├── grafana/                      # Grafana dashboards
│   └── provisioning/             # Dashboard configs
│
├── streamlit_app/                # Streamlit dashboard
│   └── Dockerfile
│
├── airflow/                      # Airflow DAGs
│   └── dags/                     # DAG definitions
│
├── scripts/                      # Utility scripts
│   ├── init-kafka-topics.sh
│   ├── init-cassandra-schema.sh
│   ├── export_vietnamese_from_cassandra.py
│   └── prepare_vozforums_dataset.py
│
├── utils/                        # Project utilities
│   └── ollama_validator.py       # Ollama validation
│
├── docker-compose.yml            # Docker service definitions
├── Dockerfile.spark              # Spark Docker image
├── run.sh                        # Main pipeline runner
├── train_vietnamese_stress.sh    # Model training script
├── test_vietnamese_model.sh      # Model testing script
└── requirements.txt              # Python dependencies
```

## Key Directories
- `producers/`: Reddit data collection with Kafka producer
- `spark/`: Spark streaming and ML inference pipelines
- `ml/models/`: Model training, inference, and checkpoints
- `cassandra/schema/`: Database schema definitions
- `airflow/dags/`: Automated retraining workflows
