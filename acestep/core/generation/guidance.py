"""
Guidance registry for ACE-Step flow matching diffusion.

Each guidance mode combines the conditional and unconditional velocity
predictions to steer generation. The model produces both predictions
via CFG batch doubling; the guidance function determines how to combine them.

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
# Guidance functions
# ---------------------------------------------------------------------------

def _clip_to_norm(guided, cond, max_ratio=3.0):
    """Fallback safety to prevent catastrophic value explosion in CFG variants."""
    std_cond = cond.std(dim=[1, 2], keepdim=True)
    std_guided = guided.std(dim=[1, 2], keepdim=True)
    
    # Check if we need to clamp (std_guided > max_ratio * std_cond)
    # Using 1e-8 to prevent division by zero
    factor = std_cond * max_ratio / (std_guided + 1e-8)
    factor = torch.clamp(factor, max=1.0)
    
    return guided * factor

def plain_cfg(pred_cond, pred_uncond, guidance_scale, **ctx):
    """Plain Classifier-Free Guidance.
    
    The standard CFG formula: uncond + scale * (cond - uncond)
    Includes a safety norm clip to prevent explosions at high scales.
    """
    guided = pred_uncond + guidance_scale * (pred_cond - pred_uncond)
    return _clip_to_norm(guided, pred_cond, max_ratio=3.0)


def cfg_pp(pred_cond, pred_uncond, guidance_scale, **ctx):
    """CFG++ — Optimized for few-step models.
    
    Instead of amplifying the full difference, CFG++ scales the correction
    by the step size dt, preventing over-correction in few-step regimes.
    Formula: cond + (scale - 1) * (cond - uncond) * |dt| / t_curr
    
    Falls back to plain CFG if dt/t_curr not available.
    """
    dt = ctx.get("dt")
    t_curr = ctx.get("sigma")
    
    # Safely extract float values from tensors if needed
    if isinstance(dt, torch.Tensor): dt = dt.item()
    if isinstance(t_curr, torch.Tensor): t_curr = t_curr.item()
    
    if dt is not None and t_curr is not None and t_curr > 1e-6:
        # Scale correction by step proportion
        step_scale = abs(dt) / t_curr
        diff = pred_cond - pred_uncond
        guided = pred_cond + (guidance_scale - 1) * diff * step_scale
        return _clip_to_norm(guided, pred_cond, max_ratio=3.0)
    else:
        # Fallback to plain CFG
        guided = pred_uncond + guidance_scale * (pred_cond - pred_uncond)
        return _clip_to_norm(guided, pred_cond, max_ratio=3.0)


def dynamic_cfg(pred_cond, pred_uncond, guidance_scale, **ctx):
    """Dynamic CFG — High guidance early, low guidance later.
    
    Decays the guidance scale across steps using cosine schedule.
    Early steps (structure) get full guidance, later steps (detail) get less.
    This produces better structure without over-saturating fine details.
    
    Effective scale: guidance_scale * cos(pi/2 * step/total)^power
    """
    step_idx = ctx.get("step_idx", 0)
    total_steps = ctx.get("total_steps", 1)
    power = 0.5  # Controls decay curve: <1 = slower decay, >1 = faster decay
    
    import math
    progress = step_idx / max(total_steps - 1, 1)
    decay = math.cos(math.pi / 2 * progress) ** power
    effective_scale = 1.0 + (guidance_scale - 1.0) * decay
    
    effective_scale = 1.0 + (guidance_scale - 1.0) * decay
    
    diff = pred_cond - pred_uncond
    guided = pred_uncond + effective_scale * diff
    return _clip_to_norm(guided, pred_cond, max_ratio=3.0)


def rescaled_cfg(pred_cond, pred_uncond, guidance_scale, **ctx):
    """Rescaled CFG — Prevents over-saturation at high guidance scales.
    
    Applies standard CFG then normalizes the output to match the standard
    deviation of the conditional prediction. This prevents the "washed out"
    or "over-saturated" artifacts that occur with high guidance scales.
    
    Formula: guided * (std(cond) / std(guided)), blended with phi parameter.
    """
    # Determine optimal blend factor (phi) based on scale
    # Higher scale requires more rescaling to prevent explosion
    phi = 0.95 if guidance_scale > 4.0 else 0.7 
    
    # Standard CFG
    guided = pred_uncond + guidance_scale * (pred_cond - pred_uncond)
    
    # Compute per-sample standard deviations (sequence and feature dims)
    std_cond = pred_cond.std(dim=[1, 2], keepdim=True)
    std_guided = guided.std(dim=[1, 2], keepdim=True)
    
    # Rescale to match conditional std, with clamp to prevent extreme blowing up
    # when std_guided is abnormally small
    factor = std_cond / (std_guided + 1e-5)
    factor = torch.clamp(factor, min=0.1, max=10.0)
    rescaled = guided * factor
    
    # Blend between pure CFG and rescaled
    return phi * rescaled + (1 - phi) * guided


def apg_guidance(pred_cond, pred_uncond, guidance_scale, **ctx):
    """APG — Adaptive Perpendicular Guidance (wrapper).
    
    Projects the guidance direction perpendicular to the conditional prediction,
    with momentum smoothing and norm thresholding.
    """
    from acestep.models.base.apg_guidance import apg_forward
    # Multi-step solvers like Heun evaluate the model multiple times per step.
    # Momentum should only be updated on the main Euler predictor step, not inside
    # intermediate `model_fn` evaluations.
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


def adg_guidance(pred_cond, pred_uncond, guidance_scale, **ctx):
    """ADG — Angle-based Dynamic Guidance (wrapper).
    
    Uses the angle between conditional and unconditional predictions
    to dynamically adjust guidance strength.
    """
    from acestep.models.base.apg_guidance import adg_forward
    latents = ctx.get("latents")
    sigma = ctx.get("sigma")
    if latents is None or sigma is None:
        # Fallback to plain CFG if missing context
        return plain_cfg(pred_cond, pred_uncond, guidance_scale, **ctx)
    return adg_forward(
        latents=latents,
        noise_pred_cond=pred_cond,
        noise_pred_uncond=pred_uncond,
        sigma=sigma,
        guidance_scale=guidance_scale,
    )


# PAG is handled separately at the handler level (perturbs attention),
# so we provide a pass-through wrapper that applies plain CFG.
def pag_guidance(pred_cond, pred_uncond, guidance_scale, **ctx):
    """PAG — Perturbed Attention Guidance (pass-through).
    
    PAG's attention perturbation is applied at the handler level.
    This wrapper applies plain CFG to the resulting predictions.
    """
    return plain_cfg(pred_cond, pred_uncond, guidance_scale, **ctx)


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
    "cfg":          {"name": "Plain CFG",    "description": "Standard classifier-free guidance"},
    "cfg_pp":       {"name": "CFG++",        "description": "Optimized for few-step models"},
    "dynamic_cfg":  {"name": "Dynamic CFG",  "description": "Decaying guidance schedule"},
    "rescaled_cfg": {"name": "Rescaled CFG", "description": "Prevents over-saturation"},
    "apg":          {"name": "APG",          "description": "Perpendicular guidance with momentum"},
    "adg":          {"name": "ADG",          "description": "Angle-based dynamic guidance"},
    "pag":          {"name": "PAG",          "description": "Perturbed attention guidance"},
}

VALID_GUIDANCE = set(GUIDANCE_MODES.keys())


def get_guidance(name: str):
    """Get a guidance function by name.
    
    Returns:
        guidance_fn callable
    
    Raises:
        ValueError if the guidance name is not recognized.
    """
    name = name.lower()
    if name not in GUIDANCE_MODES:
        valid = ", ".join(sorted(VALID_GUIDANCE))
        raise ValueError(f"Unknown guidance mode '{name}'. Valid modes: {valid}")
    return GUIDANCE_MODES[name]
