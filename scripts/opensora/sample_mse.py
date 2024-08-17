import os

import opendit
from opendit import OpenSoraConfig_mse, OpenSoraPipeline_mse


def run_pab():
    os.environ["RANK"] = "0"
    os.environ["LOCAL_RANK"] = "0"
    os.environ["WORLD_SIZE"] = "1"
    os.environ["MASTER_ADDR"] = "localhost"
    os.environ["MASTER_PORT"] = "12356"

    opendit.initialize(42)

    config = OpenSoraConfig_mse(enable_pab=True)
    pipeline = OpenSoraPipeline_mse(config)

    prompt = "a bear hunting for prey"
    video = pipeline.generate(prompt, resolution="720p").video[0]
    pipeline.save_video(video, f"./outputs/opensora_pab_{prompt}.mp4")


if __name__ == "__main__":
    run_pab()  # 01:01

# CUDA_VISIBLE_DEVICES=1 torchrun --standalone --nproc_per_node=1 scripts/opensora/sample.py
