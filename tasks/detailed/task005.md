# TASK-005: Model Inference Stub

**Owner:** ML/Spark Engineer
**Priority:** Medium
**Dependencies:** TASK-004 (Spark Structured Streaming Skeleton)
**Estimate:** 1 day

---

## Overview
Create a dummy model stub that returns random stress labels, implementing the PandasUDF pattern for distributed inference in Spark.

---

## Subtasks

### 5.1 Understand PandasUDF Pattern
**Status:** Not Started
**Type:** Research + Documentation
**Estimate:** 30 minutes

- [ ] Research Spark PandasUDF (Pandas User Defined Function)
- [ ] Understand vectorized operations
- [ ] Understand input/output types
- [ ] Document how PandasUDF works with batches
- [ ] Note performance characteristics
- [ ] Document limitations and gotchas

**Acceptance Criteria:**
- Clear understanding of PandasUDF
- Documentation created
- Ready to implement

---

### 5.2 Define Model Interface
**Status:** Not Started
**Type:** Automated
**Estimate:** 30 minutes

- [ ] Create `spark/apps/streaming/models/model_interface.py`
- [ ] Define abstract base class for models:
  - `load_model(model_path)` method
  - `predict(texts)` method
  - `get_version()` method
- [ ] Define input/output schema
- [ ] Document expected behavior

**Acceptance Criteria:**
- Interface defined clearly
- All methods documented
- Ready for implementations

---

### 5.3 Create Dummy Model
**Status:** Not Started
**Type:** Automated
**Estimate:** 1 hour

- [ ] Create `spark/apps/streaming/models/dummy_model.py`
- [ ] Implement DummyModel class:
  - Returns random stress labels (0 or 1)
  - Returns random confidence scores (0.0-1.0)
  - Model version = "dummy-v1"
- [ ] Add configurable stress ratio (default 30%)
- [ ] Implement proper interface methods
- [ ] Add logging for predictions

**Acceptance Criteria:**
- Dummy model implements interface
- Returns consistent output format
- Stress ratio is configurable
- Can run standalone

---

### 5.4 Test Dummy Model Locally
**Status:** Not Started
**Type:** Automated
**Estimate:** 30 minutes

- [ ] Create test script `test_dummy_model.py`
- [ ] Test with sample texts (10-100)
- [ ] Verify output format
- [ ] Check stress ratio distribution
- [ ] Measure inference time per record
- [ ] Test batch processing (100 records)

**Acceptance Criteria:**
- Model runs successfully
- Output format correct
- Performance acceptable (<1ms per record)

---

### 5.5 Define Output Schema
**Status:** Not Started
**Type:** Automated
**Estimate:** 20 minutes

- [ ] Update `schemas.py` with model output schema
- [ ] Add fields to existing schema:
  - stress_label (BooleanType)
  - stress_score (FloatType, 0.0-1.0)
  - model_version (StringType)
  - inference_ts (TimestampType)
- [ ] Document field meanings
- [ ] Define validation rules

**Acceptance Criteria:**
- Schema includes model output fields
- Types correct
- Documented clearly

---

### 5.6 Implement PandasUDF Wrapper
**Status:** Not Started
**Type:** Automated
**Estimate:** 2 hours

- [ ] Create `spark/apps/streaming/models/model_udf.py`
- [ ] Implement PandasUDF:
  - Input: pandas Series of text strings
  - Output: pandas DataFrame with (stress_label, stress_score, model_version)
  - Return type: StructType
- [ ] Load model in UDF (broadcasted)
- [ ] Process batch of texts
- [ ] Handle errors gracefully
- [ ] Add null handling
- [ ] Log batch statistics

**Acceptance Criteria:**
- PandasUDF processes batches correctly
- Returns proper schema
- Error handling works
- Performance acceptable

---

### 5.7 Broadcast Model to Workers
**Status:** Not Started
**Type:** Automated
**Estimate:** 1 hour

- [ ] Implement model broadcasting pattern
- [ ] Load model once per executor (not per batch)
- [ ] Use Spark broadcast variables or singleton pattern
- [ ] Test model availability across workers
- [ ] Measure memory usage

**Acceptance Criteria:**
- Model loaded once per worker
- Memory usage reasonable
- Performance improved vs loading per batch

---

### 5.8 Configure Batch Sizes
**Status:** Not Started
**Type:** Automated
**Estimate:** 30 minutes

- [ ] Configure PandasUDF batch size
- [ ] Set `spark.sql.execution.arrow.maxRecordsPerBatch`
- [ ] Test different batch sizes (32, 64, 128, 256)
- [ ] Measure:
  - Throughput (records/sec)
  - Latency per batch
  - Memory usage
- [ ] Document optimal batch size

**Acceptance Criteria:**
- Batch size configured
- Performance measured
- Optimal size documented

---

### 5.9 Integration with Streaming Pipeline
**Status:** Not Started
**Type:** Automated
**Estimate:** 1.5 hours

- [ ] Update `reddit_stream_processor.py` (TASK-004)
- [ ] Add model inference step:
  - After validation and deduplication
  - Before writing to sink
- [ ] Apply PandasUDF to text column
- [ ] Add model output columns to DataFrame
- [ ] Handle inference failures
- [ ] Add fallback for errors

**Acceptance Criteria:**
- Model inference integrated
- Pipeline runs end-to-end
- Output includes predictions
- Error handling works

---

### 5.10 Measure Inference Latency
**Status:** Not Started
**Type:** Automated
**Estimate:** 1 hour

- [ ] Add timing instrumentation
- [ ] Measure:
  - Per-record inference time
  - Per-batch inference time
  - Total UDF execution time
  - Overhead vs actual inference
- [ ] Calculate p50, p95, p99 latencies
- [ ] Document baseline metrics

**Acceptance Criteria:**
- Latency measured accurately
- Baseline metrics documented
- Inference latency <100ms per post (per PRD)

---

### 5.11 Create Model Registry Structure
**Status:** Not Started
**Type:** Automated
**Estimate:** 45 minutes

- [ ] Create directory structure:
  - `models/artifacts/` (model files)
  - `models/metadata/` (model metadata)
  - `models/configs/` (model configurations)
- [ ] Define metadata schema:
  - model_id
  - version
  - created_date
  - metrics (accuracy, precision, recall, f1)
  - training_dataset
  - framework
- [ ] Create sample metadata file

**Acceptance Criteria:**
- Directory structure created
- Metadata schema defined
- Ready for real models

---

### 5.12 Implement Model Loading Logic
**Status:** Not Started
**Type:** Automated
**Estimate:** 1 hour

- [ ] Create `models/model_loader.py`
- [ ] Implement functions:
  - `load_model_by_version(version)`
  - `load_latest_model()`
  - `list_available_models()`
- [ ] Handle model not found errors
- [ ] Add caching to avoid repeated loads
- [ ] Document usage

**Acceptance Criteria:**
- Can load models by version
- Can load latest model
- Error handling robust
- Caching works

---

### 5.13 Version Tracking in Output
**Status:** Not Started
**Type:** Automated
**Estimate:** 30 minutes

- [ ] Ensure model_version field populated
- [ ] Add model_id if needed
- [ ] Include inference_timestamp
- [ ] Test version tracking with multiple model versions
- [ ] Verify version in output data

**Acceptance Criteria:**
- Model version tracked correctly
- Can trace predictions to model version
- Useful for model comparison

---

### 5.14 Testing Framework
**Status:** Not Started
**Type:** Automated
**Estimate:** 1.5 hours

- [ ] Create `tests/test_model_inference.py`
- [ ] Test cases:
  - Dummy model predictions
  - PandasUDF with small batch
  - PandasUDF with large batch
  - Error handling in UDF
  - Null input handling
  - Integration with streaming
- [ ] Add performance tests
- [ ] Mock model for unit tests

**Acceptance Criteria:**
- All test cases pass
- Test coverage >80%
- Tests run quickly (<30s)

---

### 5.15 Monitoring and Logging
**Status:** Not Started
**Type:** Automated
**Estimate:** 45 minutes

- [ ] Add logging for:
  - Model loading events
  - Batch processing start/end
  - Prediction statistics per batch
  - Errors and failures
- [ ] Add metrics:
  - Total predictions made
  - Stress predictions count
  - Non-stress predictions count
  - Average confidence score
  - Inference time per batch

**Acceptance Criteria:**
- Comprehensive logging
- Metrics tracked
- Easy to monitor model performance

---

### 5.16 Integration Test
**Status:** Not Started
**Type:** Automated + Manual
**Estimate:** 1 hour

- [ ] Start full pipeline:
  - Kafka
  - Mock producer
  - Spark streaming with model
- [ ] Let run for 10 minutes
- [ ] **[USER TASK]** Verify in console output:
  - Predictions appear in output
  - stress_label field populated
  - stress_score in valid range (0.0-1.0)
  - model_version = "dummy-v1"
- [ ] Check Spark UI for UDF performance
- [ ] Verify no errors in logs

**Acceptance Criteria:**
- End-to-end pipeline works with model
- Predictions generated correctly
- Performance acceptable
- No errors

---

### 5.17 Performance Benchmarking
**Status:** Not Started
**Type:** Automated
**Estimate:** 1 hour

- [ ] Test with different loads:
  - 100 records/min
  - 500 records/min
  - 1000 records/min
  - 2000 records/min
- [ ] Measure for each load:
  - Processing latency
  - Throughput
  - CPU usage
  - Memory usage
- [ ] Identify bottlenecks
- [ ] Document capacity limits

**Acceptance Criteria:**
- Can handle 1000+ records/min
- Latency remains <100ms per record
- Bottlenecks identified
- Performance documented

---

### 5.18 Documentation
**Status:** Not Started
**Type:** Manual
**Estimate:** 1 hour

- [ ] Create `models/README.md`
- [ ] Document:
  - Model interface
  - How to add new models
  - PandasUDF pattern explanation
  - Performance characteristics
  - Troubleshooting guide
- [ ] Add code examples
- [ ] Document baseline metrics

**Acceptance Criteria:**
- Complete documentation
- Easy to understand
- Examples work

---

### 5.19 Prepare for Real Model
**Status:** Not Started
**Type:** Planning
**Estimate:** 30 minutes

- [ ] Document requirements for real model:
  - Input format
  - Output format
  - Size constraints (<500MB per PRD)
  - Performance requirements
- [ ] Create checklist for model integration
- [ ] Plan model replacement procedure
- [ ] Document A/B testing approach

**Acceptance Criteria:**
- Clear requirements documented
- Ready for TASK-019 (real model)

---

## Final Acceptance Criteria Checklist

- [ ] PandasUDF successfully processes batches
- [ ] Returns stress_label, stress_score, model_version fields
- [ ] Latency measured and documented (baseline)
- [ ] Inference latency <100ms per post
- [ ] Model version tracking works
- [ ] Error handling robust
- [ ] Can handle 1000+ records/minute
- [ ] All tests pass
- [ ] Documentation complete
- [ ] **[USER TASK]** Manual verification completed

---

## Dependencies for Next Tasks

This task enables:
- TASK-019: Model Selection & Fine-Tuning (will replace dummy model)
- TASK-020: Model Inference Integration (builds on this framework)
- TASK-034: Batch Size & Parallelism Optimization (uses this baseline)

---

## Rollback Plan

If this task fails:
1. Remove model inference step from pipeline
2. Pipeline can continue without predictions
3. Fix model issues separately
4. Re-integrate when ready

---

## Example PandasUDF

```python
from pyspark.sql.functions import pandas_udf
from pyspark.sql.types import StructType, StructField, BooleanType, FloatType, StringType
import pandas as pd
import random

# Define output schema
output_schema = StructType([
    StructField("stress_label", BooleanType(), False),
    StructField("stress_score", FloatType(), False),
    StructField("model_version", StringType(), False)
])

@pandas_udf(output_schema, PandasUDFType.SCALAR)
def predict_stress(texts: pd.Series) -> pd.DataFrame:
    # Dummy predictions
    predictions = []
    for text in texts:
        stress_score = random.random()
        stress_label = stress_score > 0.5
        predictions.append({
            "stress_label": stress_label,
            "stress_score": stress_score,
            "model_version": "dummy-v1"
        })
    return pd.DataFrame(predictions)
```

---

## Notes

- Dummy model provides baseline for comparison
- PandasUDF enables vectorized operations for performance
- Real model will be integrated in TASK-019/020
- Focus on framework and patterns, not model quality
- Measure everything - provides baseline for optimization
