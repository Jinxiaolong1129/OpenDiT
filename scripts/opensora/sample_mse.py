import opendit
from opendit import OpenSoraConfig_mse, OpenSoraPipeline_mse


def run_pab():
    # os.environ["CUDA_VISIBLE_DEVICES"] = "0,1,2,3"

    # os.environ["RANK"] = "0"          # 当前进程的全局排名
    # os.environ["LOCAL_RANK"] = "0"    # 当前节点的排名
    # os.environ["WORLD_SIZE"] = "3"    # 总的 GPU 数量
    # os.environ["MASTER_ADDR"] = "localhost"
    # os.environ["MASTER_PORT"] = "12356"

    opendit.initialize(42)

    config = OpenSoraConfig_mse(enable_pab=True)
    pipeline = OpenSoraPipeline_mse(config)

    prompt = "a bear hunting for prey"
    video = pipeline.generate(prompt, resolution="720p").video[0]
    pipeline.save_video(video, f"./outputs/opensora_pab_{prompt}.mp4")


if __name__ == "__main__":
    run_pab()  # 01:01

# CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 torchrun --standalone --nproc_per_node=8 scripts/opensora/sample_mse.py
