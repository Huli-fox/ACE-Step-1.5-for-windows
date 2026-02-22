"""
Guidance registry for ACE-Step flow matching diffusion.

Each guidance mode combines the conditional and unconditional velocity
predictions to steer generation. The model produces both predictions
via CFG batch doubling; the guidance function determines how to combine them.

All modes delegate to apg_forward for the actual guidance computation
(momentum smoothing, norm thresholding, perpendicular projection).
Modes differ only in the effective guidance scale they pass.

Guidance interface:
    guidance_fn(pred_cond, pred_uncond, guidance_scale, **ctx) -> vt_guided

    - pred_cond:      Conditional velocity prediction [bsz, seq, dim]
    - pred_uncond:    Unconditional velocity prediction [bsz, seq, dim]
    - guidance_scale: CFG strength (typically 3-15)
    - **ctx:          Step context (varies by mode):
        - momentum_buffer: MomentumBuffer instance (for APG)
        - latents:         Current xt (for ADG)
        - sigma:           Current timestep t_curr (for ADG)
        - dt:              Step size t_curr - t_prev (for CFG++)
        - step_idx:        Current step index (for Dynamic CFG)
        - total_steps:     Total inference steps (for Dynamic CFG)
    Returns: guided velocity prediction [bsz, seq, dim]

To add a new guidance mode:
    1. Define a function following the interface above
    2. Register it in the GUIDANCE_MODES dict
    3. Add metadata to GUIDANCE_INFO
"""

import torch
from typing import Any, Dict, Optional, Tuple


# ---------------------------------------------------------------------------
# Shared APG base
# ---------------------------------------------------------------------------

def _apg_base(pred_cond, pred_uncond, guidance_scale, **ctx):
    """Core guidance via apg_forward.

    All modes route through here to get the full APG treatment:
    momentum smoothing, norm thresholding, perpendicular projection.
    """
    from acestep.models.base.apg_guidance import apg_forward
    momentum_buffer = ctx.get("momentum_buffer")
    if ctx.get("disable_momentum", False):
        momentum_buffer = None
    return apg_forward(
        pred_cond=pred_cond,
        pred_uncond=pred_uncond,
        guidance_scale=guidance_scale,
        momentum_buffer=momentum_buffer,
        dims=[1],
    )


# ---------------------------------------------------------------------------
# Guidance functions
# ---------------------------------------------------------------------------

def plain_cfg(pred_cond, pred_uncond, guidance_scale, **ctx):
    """Plain CFG — Standard guidance strength via APG pipeline."""
    return _apg_base(pred_cond, pred_uncond, guidance_scale, **ctx)


def cfg_pp(pred_cond, pred_uncond, guidance_scale, **ctx):
    """CFG++ — Step-scaled guidance for few-step regimes.

    Reduces effective guidance proportional to step size,
    preventing over-correction in few-step schedules.
    """
    dt = ctx.get("dt")
    t_curr = ctx.get("sigma")

    if isinstance(dt, torch.Tensor): dt = dt.item()
    if isinstance(t_curr, torch.Tensor): t_curr = t_curr.item()

    if dt is not None and t_curr is not None and t_curr > 1e-6:
        step_scale = abs(dt) / t_curr
        effective_scale = 1.0 + (guidance_scale - 1.0) * step_scale
    else:
        effective_scale = guidance_scale

    return _apg_base(pred_cond, pred_uncond, effective_scale, **ctx)


def dynamic_cfg(pred_cond, pred_uncond, guidance_scale, **ctx):
    """Dynamic CFG — Cosine-decaying guidance (strong early, weak late)."""
    step_idx = ctx.get("step_idx", 0)
    total_steps = ctx.get("total_steps", 1)
    power = 0.5

    import math
    progress = step_idx / max(total_steps - 1, 1)
    decay = math.cos(math.pi / 2 * progress) ** power
    effective_scale = 1.0 + (guidance_scale - 1.0) * decay

    return _apg_base(pred_cond, pred_uncond, effective_scale, **ctx)


def rescaled_cfg(pred_cond, pred_uncond, guidance_scale, **ctx):
    """Rescaled CFG — Std-matched guidance to prevent over-saturation.

    Runs APG at the requested scale, then rescales output to match
    the conditional prediction's standard deviation.
    """
    phi = 0.95 if guidance_scale > 4.0 else 0.7

    guided = _apg_base(pred_cond, pred_uncond, guidance_scale, **ctx)

    std_cond = pred_cond.std(dim=[1, 2], keepdim=True)
    std_guided = guided.std(dim=[1, 2], keepdim=True)
    factor = std_cond / (std_guided + 1e-5)
    rescaled = guided * factor

    return phi * rescaled + (1 - phi) * guided


def apg_guidance(pred_cond, pred_uncond, guidance_scale, **ctx):
    """APG — Adaptive Perpendicular Guidance (native)."""
    return _apg_base(pred_cond, pred_uncond, guidance_scale, **ctx)


def adg_guidance(pred_cond, pred_uncond, guidance_scale, **ctx):
    """ADG — Angle-based Dynamic Guidance (wrapper)."""
    from acestep.models.base.apg_guidance import adg_forward
    latents = ctx.get("latents")
    sigma = ctx.get("sigma")
    if latents is None or sigma is None:
        return _apg_base(pred_cond, pred_uncond, guidance_scale, **ctx)
    return adg_forward(
        latents=latents,
        noise_pred_cond=pred_cond,
        noise_pred_uncond=pred_uncond,
        sigma=sigma,
        guidance_scale=guidance_scale,
    )


def pag_guidance(pred_cond, pred_uncond, guidance_scale, **ctx):
    """PAG — Perturbed Attention Guidance (attention perturbation at handler level)."""
    return _apg_base(pred_cond, pred_uncond, guidance_scale, **ctx)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

GUIDANCE_MODES = {
    "cfg": plain_cfg,
    "cfg_pp": cfg_pp,
    "dynamic_cfg": dynamic_cfg,
    "rescaled_cfg": rescaled_cfg,
    "apg": apg_guidance,
    "adg": adg_guidance,
    "pag": pag_guidance,
}

GUIDANCE_INFO = {
    "cfg":          {"name": "Plain CFG",    "description": "Standard guidance strength"},
    "cfg_pp":       {"name": "CFG++",        "description": "Step-scaled for few-step models"},
    "dynamic_cfg":  {"name": "Dynamic CFG",  "description": "Cosine-decaying guidance schedule"},
    "rescaled_cfg": {"name": "Rescaled CFG", "description": "Std-matched to prevent over-saturation"},
    "apg":          {"name": "APG",          "description": "Perpendicular guidance with momentum"},
    "adg":          {"name": "ADG",          "description": "Angle-based dynamic guidance"},
    "pag":          {"name": "PAG",          "description": "Perturbed attention guidance"},
}

VALID_GUIDANCE = set(GUIDANCE_MODES.keys())


def get_guidance(name: str):
    """Get a guidance function by name."""
    name = name.lower()
    if name not in GUIDANCE_MODES:
        valid = ", ".join(sorted(VALID_GUIDANCE))
        raise ValueError(f"Unknown guidance mode '{name}'. Valid modes: {valid}")
    return GUIDANCE_MODES[name]
