# python scripts/latte/sample_latte.py --config configs/latte/sample.yaml

# export CUDA_VISIBLE_DEVICES=1
# python scripts/latte/sample_latte.py --config configs/latte/sample_skip.yaml


respacings=(
    # "[5, 5, 5, 5, 5, 5, 5, 5, 5, 2]"
    # "[5, 5, 5, 5, 5, 5, 5, 5, 2, 2]"
    # "[2, 5, 5, 5, 5, 5, 5, 5, 5, 5]"
    # "[2, 2, 5, 5, 5, 5, 5, 5, 5, 5]"

    # "[5, 5, 5, 5, 5, 5, 5, 5, 5, 3]"
    # "[5, 5, 5, 5, 5, 5, 5, 5, 3, 3]"
    # "[5, 5, 5, 5, 5, 5, 5, 3, 3, 3]"

    # "[3, 5, 5, 5, 5, 5, 5, 5, 5, 5]"
    # "[3, 3, 5, 5, 5, 5, 5, 5, 5, 5]"
    # "[3, 3, 3, 5, 5, 5, 5, 5, 5, 5]"


    "[5, 5, 5, 5, 5, 5, 4, 4, 4, 4]"
    "[5, 5, 5, 5, 5, 4, 4, 4, 4, 4]"

    "[5, 5, 5, 5, 5, 5, 3, 3, 3, 3]"
    "[5, 5, 5, 5, 5, 3, 3, 3, 3, 3]"

    # "[5, 5, 5, 5, 5, 5, 5, 5, 3, 2]"
    "[5, 5, 5, 5, 5, 5, 5, 4, 3, 2]"

)


gpu_ids=(0 2 3 4 7)  # Assuming you have at least 4 GPUs

for i in "${!respacings[@]}"; do
    spacing="${respacings[$i]}"
    gpu_id="${gpu_ids[$i]}"

    spacing="${spacing//\[/}"
    spacing="${spacing//\]/}"
    spacing="${spacing//, /_}"

    LOG_FILE="log/log_t_respacing_$spacing.log"

    export CUDA_VISIBLE_DEVICES=$gpu_id
    echo "Inference output (for timestep_respacing: $spacing, GPU: $gpu_id) | log: $LOG_FILE"

    python scripts/latte/sample_latte.py --config configs/latte/sample_skip.yaml --timestep_respacing $spacing > $LOG_FILE 2>&1 &
done
