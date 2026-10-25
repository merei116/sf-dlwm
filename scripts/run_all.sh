#!/usr/bin/env bash
# Regenerates every table and figure of the paper from scratch.
set -e
python -m experiments.run_benchmark --config config.yaml --tag benchmark
python -m experiments.run_sweeps    --config config.yaml --sweep payload   --n-images 10
python -m experiments.run_sweeps    --config config.yaml --sweep threshold --n-images 10
python -m experiments.run_sweeps    --config config.yaml --sweep strength  --n-images 6
python -m experiments.run_ablation  --config config.yaml --n-images 10
python -m experiments.aggregate     --results results
python -m experiments.plots         --results results --figures figures
