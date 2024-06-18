#!/bin/bash

H=512
W=512

# respacings=(
#     "[10, 10, 10, 10, 10, 10, 10, 10, 5, 5]"
#     "[10, 10, 10, 10, 10, 10, 10, 5, 5, 5]"
#     "[10, 10, 10, 10, 10, 10, 5, 5, 5, 5]"
#     "[10, 10, 10, 10, 10, 5, 5, 5, 5, 5]"

#     "[10, 10, 10, 10, 10, 10, 10, 10, 2, 2]"
#     "[10, 10, 10, 10, 10, 10, 10, 2, 2, 2]"
#     "[10, 10, 10, 10, 10, 10, 2, 2, 2, 2]"
# )

# respacings=(
#     "[2, 2, 2, 2, 2, 10, 10, 10, 10, 10]"
#     "[2, 2, 2, 2, 10, 10, 10, 10, 10, 10]"
#     "[2, 2, 2, 10, 10, 10, 10, 10, 10, 10]"

#     "[2, 2, 10, 10, 10, 10, 10, 10, 10, 10]"
#     "[5, 5, 5, 5, 5, 10, 10, 10, 10, 10]"
#     "[5, 5, 5, 5, 10, 10, 10, 10, 10, 10]"
#     "[5, 5, 5, 10, 10, 10, 10, 10, 10, 10]"
# )

respacings=(
    # "[1, 1, 1, 1, 10, 10, 10, 10, 10, 10]"
    # "[1, 10, 10, 10, 10, 10, 10, 10, 10, 1]"
    # "[1, 1, 10, 10, 10, 10, 10, 10, 1, 1]"

    # "[5, 10, 10, 10, 10, 10, 10, 10, 10, 5]"
    # "[5, 5, 10, 10, 10, 10, 10, 10, 5, 5]"
    # "[5, 5, 5, 5, 10, 10, 5, 5, 5, 5]"

    "[1, 1, 1, 10, 10, 10, 10, 1, 1, 1]"
    "[2, 2, 2, 2, 10, 10, 2, 2, 2, 2]"
    "[2, 2, 2, 10, 10, 10, 10, 2, 2, 2]"
    "[2, 2, 10, 10, 10, 10, 10, 10, 2, 2]"
    "[2, 10, 10, 10, 10, 10, 10, 10, 10, 2]"
)


gpu_ids=(1 2 3 5 7)  # Assuming you have at least 4 GPUs

for i in "${!respacings[@]}"; do
    spacing="${respacings[$i]}"
    gpu_id="${gpu_ids[$i]}"

    spacing="${spacing//\[/}"
    spacing="${spacing//\]/}"
    spacing="${spacing//, /_}"

    NUM_FRAMES=16  
    FPS=24
    DTYPE=bf16
    MODEL_PATH=hpcai-tech/OpenSora-STDiT-v2-stage3

    SAVE_DIR=./samples/output_t_respacing_$spacing

    mkdir -p $SAVE_DIR

    LOG_FILE="$SAVE_DIR/log_t_respacing_$spacing.log"

    export CUDA_VISIBLE_DEVICES=$gpu_id
    echo "Inference output (for timestep_respacing: $spacing, GPU: $gpu_id) | save: $SAVE_DIR | log: $LOG_FILE"

    torchrun --standalone --nproc_per_node=1 scripts/opensora/sample_opensora_timestep_respacing.py \
        --image_size $H $W \
        --num_frames $NUM_FRAMES \
        --fps $FPS \
        --dtype $DTYPE \
        --model_pretrained_path $MODEL_PATH \
        --save_dir $SAVE_DIR \
        --enable_flashattn \
        --enable_t5_speedup > $LOG_FILE 2>&1 \
        --timestep_respacing $spacing > $LOG_FILE 2>&1 &
done
