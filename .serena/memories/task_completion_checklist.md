# Task Completion Checklist

## Before Marking a Task Complete

### Code Changes
- [ ] Code follows project naming conventions (snake_case functions, PascalCase classes)
- [ ] Docstrings added for new functions/classes
- [ ] Error handling with appropriate logging
- [ ] No hardcoded paths or credentials

### Testing
- [ ] Manual testing of changes
- [ ] Run model tests if ML code changed: `python ml/models/test_model.py`
- [ ] Check Docker containers if infrastructure changed: `docker ps`

### Integration
- [ ] Verify Kafka topics if producer modified
- [ ] Check Cassandra schema if storage modified
- [ ] Test Spark job if streaming modified

## No Formal Linting/Testing Pipeline

**Note**: This project does not have:
- No `pyproject.toml` or `setup.py`
- No configured linter (black, flake8, etc.)
- No pytest configuration
- No CI/CD pipeline

Testing is done manually through:
- `test_vietnamese_model.sh` for model validation
- `python ml/models/test_model.py` for interactive model testing
- Docker container health checks
- Log monitoring

## Quick Validation Commands

```bash
# Test model works
./test_vietnamese_model.sh

# Check Docker services
docker-compose ps

# Check producer runs
python producers/reddit_producer/main.py --test-mode --duration 10

# Verify data flow
docker exec reddit-cassandra cqlsh -e "SELECT COUNT(*) FROM reddit_rt.classified_posts_by_hour;"
```

## When Modifying ML Code

1. Train model: `./train_vietnamese_stress.sh`
2. Test model: `./test_vietnamese_model.sh`
3. Verify inference: `python ml/models/test_model.py --batch`
4. Test in Docker: `./run.sh` and monitor logs
