# Code Style and Conventions

## Python Code Style

### Naming Conventions
- **Functions**: `snake_case` (e.g., `train_epoch`, `predict_batch`, `stream_submissions`)
- **Classes**: `PascalCase` (e.g., `StressDetectionModel`, `PhoBERTMultiLabelClassifier`, `RedditStream`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `CONFIG`, `MODEL_DIR`, `TEST_FILE`)
- **Private methods**: Prefix with `_` (e.g., `_preprocess_text`, `_load_model`)

### Docstrings
- Use triple-quoted docstrings for functions and classes
- Short one-line docstrings for simple functions
- Example:
```python
def train(config):
    """Main training function"""
    ...

def evaluate(model, loader, device):
    """Evaluate model on data loader."""
    ...
```

### Type Hints
- Type hints are used sparingly in some files
- Not enforced project-wide
- Example: `def batch_test(model_path: str):`

### Logging
- Use Python's `logging` module
- Logger typically named `logger`
- Log levels: INFO for normal operations, ERROR for errors, DEBUG for verbose

### Error Handling
- Use try/except blocks with specific exceptions
- Log errors with `logger.error()` and `exc_info=True` for stack traces
- Graceful shutdown with signal handlers

## File Organization

### Import Order
1. Standard library imports
2. Third-party library imports  
3. Local application imports

### Configuration
- YAML files for configuration (`config.yaml`)
- `.env` files for secrets (Reddit credentials)
- JSON for model configs and metrics

## Shell Scripts
- Bash scripts with `#!/bin/bash` shebang
- Use `set -e` for exit on error
- Color-coded output with helper functions
- Clear step-by-step logging

## Docker
- Multi-stage builds where appropriate
- Health checks for all services
- Named volumes for persistence
- Explicit network configuration
