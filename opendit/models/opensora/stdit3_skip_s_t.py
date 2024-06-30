# Adapted from OpenSora

# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.
# --------------------------------------------------------
# References:
# OpenSora: https://github.com/hpcaitech/Open-Sora
# --------------------------------------------------------


import os

import numpy as np
import torch
import torch.nn as nn
from einops import rearrange
from timm.models.layers import DropPath
from timm.models.vision_transformer import Mlp
from transformers import PretrainedConfig, PreTrainedModel

from opendit.core.comm import (
    all_to_all_with_pad,
    gather_sequence,
    get_spatial_pad,
    get_temporal_pad,
    set_spatial_pad,
    set_temporal_pad,
    split_sequence,
)
from opendit.core.parallel_mgr import enable_sequence_parallel, get_sequence_parallel_group
from opendit.core.skip_mgr_s_t import enable_skip, if_skip_cross, if_skip_mlp, if_skip_spatial, if_skip_temporal

from .modules import (
    Attention,
    CaptionEmbedder,
    MultiHeadCrossAttention,
    PatchEmbed3D,
    PositionEmbedding2D,
    SizeEmbedder,
    T2IFinalLayer,
    TimestepEmbedder,
    approx_gelu,
    get_layernorm,
    t2i_modulate,
)
from .utils import auto_grad_checkpoint, load_checkpoint


class STDiT3Block(nn.Module):
    def __init__(
        self,
        hidden_size,
        num_heads,
        mlp_ratio=4.0,
        drop_path=0.0,
        rope=None,
        qk_norm=False,
        temporal=False,
        enable_flash_attn=False,
        block_idx=None,
    ):
        super().__init__()
        self.temporal = temporal
        self.hidden_size = hidden_size
        self.enable_flash_attn = enable_flash_attn

        attn_cls = Attention
        mha_cls = MultiHeadCrossAttention

        self.norm1 = get_layernorm(hidden_size, eps=1e-6, affine=False)
        self.attn = attn_cls(
            hidden_size,
            num_heads=num_heads,
            qkv_bias=True,
            qk_norm=qk_norm,
            rope=rope,
            enable_flash_attn=enable_flash_attn,
        )
        self.cross_attn = mha_cls(hidden_size, num_heads)
        self.norm2 = get_layernorm(hidden_size, eps=1e-6, affine=False)
        self.mlp = Mlp(
            in_features=hidden_size, hidden_features=int(hidden_size * mlp_ratio), act_layer=approx_gelu, drop=0
        )
        self.drop_path = DropPath(drop_path) if drop_path > 0.0 else nn.Identity()
        self.scale_shift_table = nn.Parameter(torch.randn(6, hidden_size) / hidden_size**0.5)

        # fast video diffusion
        self.block_idx = block_idx
        self.attn_count = 0
        self.last_attn = None
        self.cross_count = 0
        self.last_cross = None
        # mlp
        self.mlp_count = 0
        self.last_mlp = None

    def t_mask_select(self, x_mask, x, masked_x, T, S):
        # x: [B, (T, S), C]
        # mased_x: [B, (T, S), C]
        # x_mask: [B, T]
        x = rearrange(x, "B (T S) C -> B T S C", T=T, S=S)
        masked_x = rearrange(masked_x, "B (T S) C -> B T S C", T=T, S=S)
        x = torch.where(x_mask[:, :, None, None], x, masked_x)
        x = rearrange(x, "B T S C -> B (T S) C")
        return x

    def forward(
        self,
        x,
        y,
        t,
        mask=None,  # text mask
        x_mask=None,  # temporal mask
        t0=None,  # t with timestamp=0
        T=None,  # number of frames
        S=None,  # number of pixel patches
        timestep=None,
        mlp_outputs=None,
        all_timesteps=None,
    ):
        # prepare modulate parameters
        B, N, C = x.shape
        shift_msa, scale_msa, gate_msa, shift_mlp, scale_mlp, gate_mlp = (
            self.scale_shift_table[None] + t.reshape(B, 6, -1)
        ).chunk(6, dim=1)
        if x_mask is not None:
            shift_msa_zero, scale_msa_zero, gate_msa_zero, shift_mlp_zero, scale_mlp_zero, gate_mlp_zero = (
                self.scale_shift_table[None] + t0.reshape(B, 6, -1)
            ).chunk(6, dim=1)

        if self.temporal:
            skip_attn, self.attn_count = if_skip_temporal(int(timestep[0]), self.attn_count)
        else:
            skip_attn, self.attn_count = if_skip_spatial(int(timestep[0]), self.attn_count, self.block_idx)

        if skip_attn:
            x_m_s = self.last_attn
        else:
            # modulate (attention)
            x_m = t2i_modulate(self.norm1(x), shift_msa, scale_msa)
            if x_mask is not None:
                x_m_zero = t2i_modulate(self.norm1(x), shift_msa_zero, scale_msa_zero)
                x_m = self.t_mask_select(x_mask, x_m, x_m_zero, T, S)

            # attention
            if self.temporal:
                if enable_sequence_parallel():
                    x_m, S, T = self.dynamic_switch(x_m, S, T, to_spatial_shard=True)
                x_m = rearrange(x_m, "B (T S) C -> (B S) T C", T=T, S=S)
                x_m = self.attn(x_m)
                x_m = rearrange(x_m, "(B S) T C -> B (T S) C", T=T, S=S)
                if enable_sequence_parallel():
                    x_m, S, T = self.dynamic_switch(x_m, S, T, to_spatial_shard=False)
            else:
                x_m = rearrange(x_m, "B (T S) C -> (B T) S C", T=T, S=S)
                x_m = self.attn(x_m)
                x_m = rearrange(x_m, "(B T) S C -> B (T S) C", T=T, S=S)

            # modulate (attention)
            x_m_s = gate_msa * x_m
            if x_mask is not None:
                x_m_s_zero = gate_msa_zero * x_m
                x_m_s = self.t_mask_select(x_mask, x_m_s, x_m_s_zero, T, S)

            if enable_skip():
                self.last_attn = x_m_s

        # residual
        x = x + self.drop_path(x_m_s)

        # cross attention
        skip_cross, self.cross_count = if_skip_cross(int(timestep[0]), self.cross_count)
        if skip_cross:
            x = x + self.last_cross
        else:
            x_cross = self.cross_attn(x, y, mask)
            if enable_skip():
                self.last_cross = x_cross
            x = x + x_cross

        # TODO: skip MLP self.temporal=True (time block)
        skip_mlp, self.mlp_count, skip_next, skip_start_t = if_skip_mlp(
            int(timestep[0]), self.mlp_count, self.block_idx, all_timesteps
        )

        if skip_mlp:
            x_m_s = mlp_outputs.get((skip_start_t, self.block_idx), None) if mlp_outputs is not None else None
            if x_m_s is not None:
                if self.temporal:
                    print(
                        f"Skip | Using stored MLP output | Time | t {int(timestep[0])} | start_t {skip_start_t} | block {self.block_idx}"
                    )
                else:
                    print(
                        f"Skip | Using stored MLP output | Spatial | t {int(timestep[0])} | start_t {skip_start_t} | block {self.block_idx}"
                    )

                del mlp_outputs[(skip_start_t, self.block_idx)]
            else:
                raise ValueError(
                    f"No stored MLP output found | t {int(timestep[0])} | start_t {skip_start_t} | block {self.block_idx}"
                )
        else:
            # modulate (MLP)
            x_m = t2i_modulate(self.norm2(x), shift_mlp, scale_mlp)
            if x_mask is not None:
                x_m_zero = t2i_modulate(self.norm2(x), shift_mlp_zero, scale_mlp_zero)
                x_m = self.t_mask_select(x_mask, x_m, x_m_zero, T, S)

            # MLP
            x_m = self.mlp(x_m)

            # modulate (MLP)
            x_m_s = gate_mlp * x_m
            if x_mask is not None:
                x_m_s_zero = gate_mlp_zero * x_m
                x_m_s = self.t_mask_select(x_mask, x_m_s, x_m_s_zero, T, S)
            if skip_next:
                if mlp_outputs is not None:
                    mlp_outputs[(int(timestep[0]), self.block_idx)] = x_m_s

        # residual
        x = x + self.drop_path(x_m_s)

        return x, mlp_outputs

    def dynamic_switch(self, x, s, t, to_spatial_shard: bool):
        if to_spatial_shard:
            scatter_dim, gather_dim = 2, 1
            scatter_pad = get_spatial_pad()
            gather_pad = get_temporal_pad()
        else:
            scatter_dim, gather_dim = 1, 2
            scatter_pad = get_temporal_pad()
            gather_pad = get_spatial_pad()

        x = rearrange(x, "b (t s) d -> b t s d", t=t, s=s)
        x = all_to_all_with_pad(
            x,
            get_sequence_parallel_group(),
            scatter_dim=scatter_dim,
            gather_dim=gather_dim,
            scatter_pad=scatter_pad,
            gather_pad=gather_pad,
        )
        new_s, new_t = x.shape[2], x.shape[1]
        x = rearrange(x, "b t s d -> b (t s) d")
        return x, new_s, new_t


class STDiT3Config(PretrainedConfig):
    model_type = "STDiT3"

    def __init__(
        self,
        input_size=(None, None, None),
        input_sq_size=512,
        in_channels=4,
        patch_size=(1, 2, 2),
        hidden_size=1152,
        depth=28,
        num_heads=16,
        mlp_ratio=4.0,
        class_dropout_prob=0.1,
        pred_sigma=True,
        drop_path=0.0,
        caption_channels=4096,
        model_max_length=300,
        qk_norm=True,
        enable_flash_attn=False,
        only_train_temporal=False,
        freeze_y_embedder=False,
        skip_y_embedder=False,
        **kwargs,
    ):
        self.input_size = input_size
        self.input_sq_size = input_sq_size
        self.in_channels = in_channels
        self.patch_size = patch_size
        self.hidden_size = hidden_size
        self.depth = depth
        self.num_heads = num_heads
        self.mlp_ratio = mlp_ratio
        self.class_dropout_prob = class_dropout_prob
        self.pred_sigma = pred_sigma
        self.drop_path = drop_path
        self.caption_channels = caption_channels
        self.model_max_length = model_max_length
        self.qk_norm = qk_norm
        self.enable_flash_attn = enable_flash_attn
        self.only_train_temporal = only_train_temporal
        self.freeze_y_embedder = freeze_y_embedder
        self.skip_y_embedder = skip_y_embedder
        super().__init__(**kwargs)


class STDiT3(PreTrainedModel):
    config_class = STDiT3Config

    def __init__(self, config):
        super().__init__(config)
        self.pred_sigma = config.pred_sigma
        self.in_channels = config.in_channels
        self.out_channels = config.in_channels * 2 if config.pred_sigma else config.in_channels

        # model size related
        self.depth = config.depth
        self.mlp_ratio = config.mlp_ratio
        self.hidden_size = config.hidden_size
        self.num_heads = config.num_heads

        # computation related
        self.drop_path = config.drop_path
        self.enable_flash_attn = config.enable_flash_attn

        # input size related
        self.patch_size = config.patch_size
        self.input_sq_size = config.input_sq_size
        self.pos_embed = PositionEmbedding2D(config.hidden_size)

        from rotary_embedding_torch import RotaryEmbedding

        self.rope = RotaryEmbedding(dim=self.hidden_size // self.num_heads)

        # embedding
        self.x_embedder = PatchEmbed3D(config.patch_size, config.in_channels, config.hidden_size)
        self.t_embedder = TimestepEmbedder(config.hidden_size)
        self.fps_embedder = SizeEmbedder(self.hidden_size)
        self.t_block = nn.Sequential(
            nn.SiLU(),
            nn.Linear(config.hidden_size, 6 * config.hidden_size, bias=True),
        )
        self.y_embedder = CaptionEmbedder(
            in_channels=config.caption_channels,
            hidden_size=config.hidden_size,
            uncond_prob=config.class_dropout_prob,
            act_layer=approx_gelu,
            token_num=config.model_max_length,
        )

        # spatial blocks
        drop_path = [x.item() for x in torch.linspace(0, self.drop_path, config.depth)]
        self.spatial_blocks = nn.ModuleList(
            [
                STDiT3Block(
                    hidden_size=config.hidden_size,
                    num_heads=config.num_heads,
                    mlp_ratio=config.mlp_ratio,
                    drop_path=drop_path[i],
                    qk_norm=config.qk_norm,
                    enable_flash_attn=config.enable_flash_attn,
                    block_idx=i,
                )
                for i in range(config.depth)
            ]
        )

        # temporal blocks
        drop_path = [x.item() for x in torch.linspace(0, self.drop_path, config.depth)]
        self.temporal_blocks = nn.ModuleList(
            [
                STDiT3Block(
                    hidden_size=config.hidden_size,
                    num_heads=config.num_heads,
                    mlp_ratio=config.mlp_ratio,
                    drop_path=drop_path[i],
                    qk_norm=config.qk_norm,
                    enable_flash_attn=config.enable_flash_attn,
                    # temporal
                    temporal=True,
                    rope=self.rope.rotate_queries_or_keys,
                    block_idx=i,
                )
                for i in range(config.depth)
            ]
        )
        # BUG mlp outputs for skip
        self.spatial_mlp_outputs = {}
        self.temporal_mlp_outputs = {}
        # final layer
        self.final_layer = T2IFinalLayer(config.hidden_size, np.prod(self.patch_size), self.out_channels)

        self.initialize_weights()
        if config.only_train_temporal:
            for param in self.parameters():
                param.requires_grad = False
            for block in self.temporal_blocks:
                for param in block.parameters():
                    param.requires_grad = True

        if config.freeze_y_embedder:
            for param in self.y_embedder.parameters():
                param.requires_grad = False

    def initialize_weights(self):
        # Initialize transformer layers:
        def _basic_init(module):
            if isinstance(module, nn.Linear):
                torch.nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.constant_(module.bias, 0)

        self.apply(_basic_init)

        # Initialize fps_embedder
        nn.init.normal_(self.fps_embedder.mlp[0].weight, std=0.02)
        nn.init.constant_(self.fps_embedder.mlp[0].bias, 0)
        nn.init.constant_(self.fps_embedder.mlp[2].weight, 0)
        nn.init.constant_(self.fps_embedder.mlp[2].bias, 0)

        # Initialize timporal blocks
        for block in self.temporal_blocks:
            nn.init.constant_(block.attn.proj.weight, 0)
            nn.init.constant_(block.cross_attn.proj.weight, 0)
            nn.init.constant_(block.mlp.fc2.weight, 0)

    def get_dynamic_size(self, x):
        _, _, T, H, W = x.size()
        if T % self.patch_size[0] != 0:
            T += self.patch_size[0] - T % self.patch_size[0]
        if H % self.patch_size[1] != 0:
            H += self.patch_size[1] - H % self.patch_size[1]
        if W % self.patch_size[2] != 0:
            W += self.patch_size[2] - W % self.patch_size[2]
        T = T // self.patch_size[0]
        H = H // self.patch_size[1]
        W = W // self.patch_size[2]
        return (T, H, W)

    def encode_text(self, y, mask=None):
        y = self.y_embedder(y, self.training)  # [B, 1, N_token, C]
        if mask is not None:
            if mask.shape[0] != y.shape[0]:
                mask = mask.repeat(y.shape[0] // mask.shape[0], 1)
            mask = mask.squeeze(1).squeeze(1)
            y = y.squeeze(1).masked_select(mask.unsqueeze(-1) != 0).view(1, -1, self.hidden_size)
            y_lens = mask.sum(dim=1).tolist()
        else:
            y_lens = [y.shape[2]] * y.shape[0]
            y = y.squeeze(1).view(1, -1, self.hidden_size)
        return y, y_lens

    def forward(
        self, x, timestep, all_timesteps, y, mask=None, x_mask=None, fps=None, height=None, width=None, **kwargs
    ):
        dtype = self.x_embedder.proj.weight.dtype
        B = x.size(0)
        x = x.to(dtype)
        timestep = timestep.to(dtype)
        y = y.to(dtype)

        # === get pos embed ===
        _, _, Tx, Hx, Wx = x.size()
        T, H, W = self.get_dynamic_size(x)
        S = H * W
        base_size = round(S**0.5)
        resolution_sq = (height[0].item() * width[0].item()) ** 0.5
        scale = resolution_sq / self.input_sq_size
        pos_emb = self.pos_embed(x, H, W, scale=scale, base_size=base_size)

        # === get timestep embed ===
        t = self.t_embedder(timestep, dtype=x.dtype)  # [B, C]
        fps = self.fps_embedder(fps.unsqueeze(1), B)
        t = t + fps
        t_mlp = self.t_block(t)
        t0 = t0_mlp = None
        if x_mask is not None:
            t0_timestep = torch.zeros_like(timestep)
            t0 = self.t_embedder(t0_timestep, dtype=x.dtype)
            t0 = t0 + fps
            t0_mlp = self.t_block(t0)

        # === get y embed ===
        if self.config.skip_y_embedder:
            y_lens = mask
            if isinstance(y_lens, torch.Tensor):
                y_lens = y_lens.long().tolist()
        else:
            y, y_lens = self.encode_text(y, mask)

        # === get x embed ===
        x = self.x_embedder(x)  # [B, N, C]
        x = rearrange(x, "B (T S) C -> B T S C", T=T, S=S)
        x = x + pos_emb

        # shard over the sequence dim if sp is enabled
        if enable_sequence_parallel():
            set_temporal_pad(T)
            set_spatial_pad(S)
            x = split_sequence(x, get_sequence_parallel_group(), dim=1, grad_scale="down", pad=get_temporal_pad())
            T = x.shape[1]
            x_mask_org = x_mask
            x_mask = split_sequence(
                x_mask, get_sequence_parallel_group(), dim=1, grad_scale="down", pad=get_temporal_pad()
            )

        x = rearrange(x, "B T S C -> B (T S) C", T=T, S=S)

        # === blocks ===
        for spatial_block, temporal_block in zip(self.spatial_blocks, self.temporal_blocks):
            # x = auto_grad_checkpoint(spatial_block, x, y, t_mlp, y_lens, x_mask, t0_mlp, T, S, timestep)
            # x = auto_grad_checkpoint(temporal_block, x, y, t_mlp, y_lens, x_mask, t0_mlp, T, S, timestep)

            x, self.spatial_mlp_outputs = auto_grad_checkpoint(
                spatial_block,
                x,
                y,
                t_mlp,
                y_lens,
                x_mask,
                t0_mlp,
                T,
                S,
                timestep,
                mlp_outputs=self.spatial_mlp_outputs,
                all_timesteps=all_timesteps,
            )

            x, self.temporal_mlp_outputs = auto_grad_checkpoint(
                temporal_block,
                x,
                y,
                t_mlp,
                y_lens,
                x_mask,
                t0_mlp,
                T,
                S,
                timestep,
                mlp_outputs=self.temporal_mlp_outputs,
                all_timesteps=all_timesteps,
            )

        if enable_sequence_parallel():
            x = rearrange(x, "B (T S) C -> B T S C", T=T, S=S)
            x = gather_sequence(x, get_sequence_parallel_group(), dim=1, grad_scale="up", pad=get_temporal_pad())
            T, S = x.shape[1], x.shape[2]
            x = rearrange(x, "B T S C -> B (T S) C", T=T, S=S)
            x_mask = x_mask_org

        # === final layer ===
        x = self.final_layer(x, t, x_mask, t0, T, S)
        x = self.unpatchify(x, T, H, W, Tx, Hx, Wx)

        # cast to float32 for better accuracy
        x = x.to(torch.float32)
        return x

    def unpatchify(self, x, N_t, N_h, N_w, R_t, R_h, R_w):
        """
        Args:
            x (torch.Tensor): of shape [B, N, C]

        Return:
            x (torch.Tensor): of shape [B, C_out, T, H, W]
        """

        # N_t, N_h, N_w = [self.input_size[i] // self.patch_size[i] for i in range(3)]
        T_p, H_p, W_p = self.patch_size
        x = rearrange(
            x,
            "B (N_t N_h N_w) (T_p H_p W_p C_out) -> B C_out (N_t T_p) (N_h H_p) (N_w W_p)",
            N_t=N_t,
            N_h=N_h,
            N_w=N_w,
            T_p=T_p,
            H_p=H_p,
            W_p=W_p,
            C_out=self.out_channels,
        )
        # unpad
        x = x[:, :, :R_t, :R_h, :R_w]
        return x


def STDiT3_XL_2_skip(from_pretrained=None, **kwargs):
    if from_pretrained is not None and not os.path.isdir(from_pretrained):
        model = STDiT3.from_pretrained(from_pretrained, **kwargs)
    else:
        config = STDiT3Config(depth=28, hidden_size=1152, patch_size=(1, 2, 2), num_heads=16, **kwargs)
        model = STDiT3(config)
        if from_pretrained is not None:
            load_checkpoint(model, from_pretrained)
    return model
