from utils import generate_func, read_prompt_list

import opendit
from opendit import OpenSoraConfig, OpenSoraPipeline
from opendit.models.opensora import OpenSoraPABConfig


def wo_spatial(prompt_list):
    pab_config = OpenSoraPABConfig(spatial_broadcast=False)
    config = OpenSoraConfig(enable_pab=True, pab_config=pab_config)
    pipeline = OpenSoraPipeline(config)

    generate_func(pipeline, prompt_list, "./samples/wo_spatial", loop=1)


def wo_temporal(prompt_list):
    pab_config = OpenSoraPABConfig(temporal_broadcast=False)
    config = OpenSoraConfig(enable_pab=True, pab_config=pab_config)
    pipeline = OpenSoraPipeline(config)

    generate_func(pipeline, prompt_list, "./samples/wo_temporal", loop=1)


def wo_cross(prompt_list):
    pab_config = OpenSoraPABConfig(cross_broadcast=False)
    config = OpenSoraConfig(enable_pab=True, pab_config=pab_config)
    pipeline = OpenSoraPipeline(config)

    generate_func(pipeline, prompt_list, "./samples/wo_cross", loop=1)


def wo_mlp(prompt_list):
    pab_config = OpenSoraPABConfig(mlp_skip=False)
    config = OpenSoraConfig(enable_pab=True, pab_config=pab_config)
    pipeline = OpenSoraPipeline(config)

    generate_func(pipeline, prompt_list, "./samples/wo_mlp", loop=1)


if __name__ == "__main__":
    opendit.initialize(42)
    prompt_list = read_prompt_list("vbench/VBench_full_info_test.json")
    wo_spatial(prompt_list)
    wo_temporal(prompt_list)
    wo_cross(prompt_list)
    wo_mlp(prompt_list)
