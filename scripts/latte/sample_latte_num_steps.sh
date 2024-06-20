#!/bin/bash

num_steps=(100 200 500)

gpu_ids=(0 1 2)  # Assuming you have at least 4 GPUs

for i in "${!num_steps[@]}"; do
    gpu_id="${gpu_ids[$i]}"
    num_step="${num_steps[$i]}"

    LOG_FILE="log/log_t_step_$num_step.log"

    export CUDA_VISIBLE_DEVICES=$gpu_id
    echo "Inference output (for num_step: $num_step, GPU: $gpu_id) | save: $SAVE_DIR | log: $LOG_FILE"

    python scripts/latte/sample_latte_num_steps.py --config configs/latte/sample_skip.yaml --num_sampling_steps $num_step > $LOG_FILE 2>&1 &
done
