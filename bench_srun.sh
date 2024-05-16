WARMUP=20
RUNTIME=20
BATCH_SIZE=1

# frame, hw, sp_size
HYPE_LIST=(
    # "(32 512 2)" # 64k
    # "(128 1024 2)"
    # "(256 1536 4)"
    "(512 2048 8)"
    "(1024 3072 8)"
)
GPU_NUM=16
# sp_list=("dsp" "megatron" "ulysses")
sp_list=("dsp")

for hype in "${HYPE_LIST[@]}"
do
    read -r NUM_FRAMES H SP_SIZE <<<"${hype//[()]/}"
    W=$H
    for SP in ${sp_list[@]}
    do
        bash scripts/opensora/bench_opensora_srun.sh xx $GPU_NUM test_ds $WARMUP $RUNTIME $BATCH_SIZE $NUM_FRAMES $H $W $SP $SP_SIZE
    done
done
