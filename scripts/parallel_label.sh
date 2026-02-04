#!/bin/bash
# Parallel labeling - splits data and runs N workers

WORKERS=${1:-3}
INPUT="data/cleaned/voz_cleaned.jsonl"
OUTPUT_DIR="data/labeled/parallel"

mkdir -p $OUTPUT_DIR

# Count lines and split
TOTAL=$(wc -l < $INPUT)
PER_WORKER=$((TOTAL / WORKERS + 1))

echo "Total: $TOTAL, Workers: $WORKERS, Per worker: ~$PER_WORKER"

# Split input file
split -l $PER_WORKER $INPUT ${OUTPUT_DIR}/chunk_

# Run workers in parallel
i=0
for chunk in ${OUTPUT_DIR}/chunk_*; do
    output="${OUTPUT_DIR}/labels_${i}.jsonl"
    echo "Starting worker $i: $chunk -> $output"
    python3 scripts/qwen_labeling.py --input "$chunk" --output "$output" --no-resume &
    ((i++))
done

echo "All $WORKERS workers started. Monitor with: ls -la $OUTPUT_DIR/*.jsonl"
echo "Merge when done: cat ${OUTPUT_DIR}/labels_*.jsonl > data/labeled/qwen_labels_full.jsonl"

wait
echo "All workers finished!"
