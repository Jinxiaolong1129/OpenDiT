WARMUP=$4
RUNTIME=$5
BATCH_SIZE=$6
NUM_FRAMES=$7
H=$8
W=$9
SP=${10}
SP_SIZE=${11}
MODEL_TYPE=${12}

source bash_slurm_env.sh

mkdir -p log

echo "run WARMUP=$WARMUP RUNTIME=$RUNTIME BATCH_SIZE=$BATCH_SIZE NUM_FRAMES=$NUM_FRAMES H=$H W=$W SP=$SP SP_SIZE=$SP_SIZE MODEL_TYPE=$MODEL_TYPE"
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True srun -N${NUM_NODES} --gres=gpu:${GRES} --ntasks-per-node=1 --cpus-per-task=${CPUS} -t 00:15:00 --job-name=$3 --mem=0 \
torchrun --standalone --nproc_per_node=$GRES scripts/opensora/bench_opensora.py \
    --batch_size $BATCH_SIZE \
    --mixed_precision bf16 \
    --grad_checkpoint \
    --data_path "./videos/demo.csv" \
    --text_speedup \
    --enable_flashattn \
    --enable_layernorm_kernel \
    --warmup $WARMUP \
    --runtime $RUNTIME \
    --num_frames $NUM_FRAMES \
    --image_size $H $W \
    --sp $SP \
    --model_type $MODEL_TYPE \
    --sequence_parallel_size $SP_SIZE | tee log/batch${BATCH_SIZE}_f${NUM_FRAMES}_h${H}_w${W}_sp${SP_SIZE}_${SP}.log
