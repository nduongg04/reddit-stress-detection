"""
Configuration loader for Reddit producer
"""
import yaml
import os
from pathlib import Path


class Config:
    """Load and validate configuration from YAML file"""

    def __init__(self, config_path=None):
        if config_path is None:
            config_path = Path(__file__).parent / 'config.yaml'

        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.validate()

    def validate(self):
        """Validate configuration has required fields"""
        required_sections = ['reddit', 'kafka', 'producer', 'rate_limiting']

        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required config section: {section}")

        # Validate Reddit config
        if not self.config['reddit'].get('subreddits'):
            raise ValueError("At least one subreddit must be specified")

        # Override Kafka bootstrap_servers from environment variable if set
        kafka_servers_env = os.environ.get('KAFKA_BOOTSTRAP_SERVERS')
        if kafka_servers_env:
            self.config['kafka']['bootstrap_servers'] = kafka_servers_env.split(',')

        # Validate Kafka config
        if not self.config['kafka'].get('bootstrap_servers'):
            raise ValueError("Kafka bootstrap_servers must be specified")

        if not self.config['kafka'].get('topic'):
            raise ValueError("Kafka topic must be specified")

    def get(self, key, default=None):
        """Get configuration value by key (supports nested keys with dot notation)"""
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default

        return value

    def __getitem__(self, key):
        """Allow dict-like access to config"""
        return self.config[key]

    def to_dict(self):
        """Return config as dictionary"""
        return self.config.copy()
