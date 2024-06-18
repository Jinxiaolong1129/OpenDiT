#!/bin/bash

H=512
W=512

num_steps=(100)

gpu_ids=(7)  # Assuming you have at least 4 GPUs

for i in "${!num_steps[@]}"; do
    gpu_id="${gpu_ids[$i]}"
    num_step="${num_steps[$i]}"

    NUM_FRAMES=16  
    FPS=24
    DTYPE=bf16
    MODEL_PATH=hpcai-tech/OpenSora-STDiT-v2-stage3

    SAVE_DIR=./samples/output_t_step_$num_step

    mkdir -p $SAVE_DIR

    LOG_FILE="$SAVE_DIR/log_t_step_$num_step.log"

    export CUDA_VISIBLE_DEVICES=$gpu_id
    echo "Inference output (for num_step: $num_step, GPU: $gpu_id) | save: $SAVE_DIR | log: $LOG_FILE"

    torchrun --standalone --nproc_per_node=1 scripts/opensora/sample_opensora_num_steps.py \
        --image_size $H $W \
        --num_frames $NUM_FRAMES \
        --fps $FPS \
        --dtype $DTYPE \
        --model_pretrained_path $MODEL_PATH \
        --save_dir $SAVE_DIR \
        --enable_flashattn \
        --enable_t5_speedup > $LOG_FILE 2>&1 \
        --scheduler_num_sampling_steps $num_step > $LOG_FILE 2>&1 &
done
