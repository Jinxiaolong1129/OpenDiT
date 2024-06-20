import torch
import numpy as np

# def space_timesteps(num_timesteps, section_counts):
#     """
#     Create a list of timesteps to use from an original diffusion process,
#     given the number of timesteps we want to take from equally-sized portions
#     of the original process.
#     For example, if there's 300 timesteps and the section counts are [10,15,20]
#     then the first 100 timesteps are strided to be 10 timesteps, the second 100
#     are strided to be 15 timesteps, and the final 100 are strided to be 20.
#     If the stride is a string starting with "ddim", then the fixed striding
#     from the DDIM paper is used, and only one section is allowed.
#     :param num_timesteps: the number of diffusion steps in the original
#                           process to divide up.
#     :param section_counts: either a list of numbers, or a string containing
#                            comma-separated numbers, indicating the step count
#                            per section. As a special case, use "ddimN" where N
#                            is a number of steps to use the striding from the
#                            DDIM paper.
#     :return: a set of diffusion steps from the original process to use.
#     """
#     if isinstance(section_counts, str):
#         if section_counts.startswith("ddim"):
#             desired_count = int(section_counts[len("ddim") :])
#             for i in range(1, num_timesteps):
#                 if len(range(0, num_timesteps, i)) == desired_count:
#                     return set(range(0, num_timesteps, i))
#             raise ValueError(f"cannot create exactly {num_timesteps} steps with an integer stride")
#         section_counts = [int(x) for x in section_counts.split(",")]
#     size_per = num_timesteps // len(section_counts)
#     extra = num_timesteps % len(section_counts)
#     start_idx = 0
#     all_steps = []
#     for i, section_count in enumerate(section_counts):
#         size = size_per + (1 if i < extra else 0)
#         if size < section_count:
#             raise ValueError(f"cannot divide section of {size} steps into {section_count}")
#         if section_count <= 1:
#             frac_stride = 1
#         else:
#             frac_stride = (size - 1) / (section_count - 1)
#         cur_idx = 0.0
#         taken_steps = []
#         for _ in range(section_count):
#             taken_steps.append(start_idx + round(cur_idx))
#             cur_idx += frac_stride
#         all_steps += taken_steps
#         start_idx += size
#     # return set(all_steps)

#     sorted_tensor = torch.tensor(all_steps, dtype=torch.int).sort(descending=True).values
#     return sorted_tensor



def space_timesteps(time_steps, time_bins):
    num_bins = len(time_bins)
    bin_size = time_steps // num_bins
    
    result = []
    
    for i, bin_count in enumerate(time_bins):
        start = i * bin_size
        # end = start + bin_size - 1
        end = start + bin_size
        
        # 生成每个bin的时间步长
        bin_steps = np.linspace(start, end, bin_count, endpoint=False, dtype=int).tolist()
        result.extend(bin_steps)
    
    # 将结果转换为torch tensor并从大到小排序
    result_tensor = torch.tensor(result, dtype=torch.int32)
    sorted_tensor = torch.sort(result_tensor, descending=True).values
    
    return sorted_tensor
