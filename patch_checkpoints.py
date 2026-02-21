"""
Checkpoint Model Patcher for ACE-Step
=====================================

Surgically patches checkpoint `modeling_acestep_v15_base.py` files to integrate
the solver and guidance plugin registries. Only modifies the specific lines
required — does NOT overwrite files wholesale.

Idempotent: safe to run multiple times; skips already-patched files.

Usage:
    python patch_checkpoints.py [--checkpoints-dir <path>] [--dry-run]
"""

import argparse
import os
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Patch definitions
# ---------------------------------------------------------------------------
# Each patch is (description, old_pattern, new_replacement, already_patched_marker)
# old_pattern is a regex; new_replacement is the literal replacement string.
# already_patched_marker is a string that, if found in the file, means this
# patch was already applied and should be skipped.

PATCHES = [
    # --- 1. Replace use_adg parameter with guidance_mode ---
    {
        "name": "generate_audio signature: use_adg → guidance_mode",
        "marker": "guidance_mode: str =",
        "pattern": r"        use_adg: bool = False,",
        "replacement": "        guidance_mode: str = \"apg\",",
    },

    # --- 2. Add solver + guidance imports after solver import ---
    {
        "name": "Add guidance import alongside solver import",
        "marker": "from acestep.core.generation.guidance import",
        "pattern": (
            r"        from acestep\.core\.generation\.solvers import get_solver, VALID_SOLVERS\n"
        ),
        "replacement": (
            "        from acestep.core.generation.solvers import get_solver, VALID_SOLVERS\n"
            "        from acestep.core.generation.guidance import get_guidance, VALID_GUIDANCE\n"
        ),
    },

    # --- 3. Add guidance function init after solver init ---
    {
        "name": "Add guidance_fn initialization",
        "marker": "guidance_fn = get_guidance",
        "pattern": (
            r"        solver_fn, needs_model_fn = get_solver\(solver_name\)\n\n"
            r"        # Build model_fn"
        ),
        "replacement": (
            "        solver_fn, needs_model_fn = get_solver(solver_name)\n"
            "\n"
            "        # Get guidance function\n"
            "        _gm = guidance_mode if guidance_mode else \"apg\"\n"
            "        # Legacy: if use_adg was passed via kwargs, map accordingly\n"
            "        if kwargs.get(\"use_adg\", False) and _gm == \"apg\":\n"
            "            _gm = \"adg\"\n"
            "        guidance_fn = get_guidance(_gm)\n"
            "\n"
            "        # Build model_fn"
        ),
    },

    # --- 4. Replace model_fn's use_adg_flag with g_fn ---
    {
        "name": "model_fn callback: use_adg_flag → g_fn",
        "marker": "g_fn, cfg_start, cfg_end",
        "pattern": (
            r"                               context_lat, guidance_scale, use_adg_flag, cfg_start, cfg_end,"
        ),
        "replacement": (
            "                               context_lat, guidance_scale, g_fn, cfg_start, cfg_end,"
        ),
    },

    # --- 5. Replace inline APG/ADG in model_fn with g_fn call ---
    {
        "name": "model_fn callback: inline APG/ADG → g_fn call",
        "marker": "vt_inner = g_fn(",
        "pattern": (
            r"                        if apply_cfg:\n"
            r"                            if not use_adg_flag:\n"
            r"                                vt_inner = apg_forward\(\n"
            r"                                    pred_cond=p_cond, pred_uncond=p_uncond,\n"
            r"                                    guidance_scale=guidance_scale,\n"
            r"                                    momentum_buffer=momentum_buf, dims=\[1\],\n"
            r"                                \)\n"
            r"                            else:\n"
            r"                                vt_inner = adg_forward\(\n"
            r"                                    latents=xt_inner, noise_pred_cond=p_cond,\n"
            r"                                    noise_pred_uncond=p_uncond, sigma=t_val,\n"
            r"                                    guidance_scale=guidance_scale,\n"
            r"                                \)"
        ),
        "replacement": (
            "                        if apply_cfg:\n"
            "                            vt_inner = g_fn(\n"
            "                                p_cond, p_uncond, guidance_scale,\n"
            "                                momentum_buffer=momentum_buf,\n"
            "                                disable_momentum=True,\n"
            "                                latents=xt_inner, sigma=t_val,\n"
            "                            )"
        ),
    },

    # --- 6. Replace use_adg in _make_model_fn call with guidance_fn ---
    {
        "name": "_make_model_fn call: use_adg → guidance_fn",
        "marker": "guidance_fn, cfg_interval_start, cfg_interval_end",
        "pattern": (
            r"                diffusion_guidance_sale, use_adg, cfg_interval_start, cfg_interval_end,"
        ),
        "replacement": (
            "                diffusion_guidance_sale, guidance_fn, cfg_interval_start, cfg_interval_end,"
        ),
    },

    # --- 7. Replace inline APG/ADG in main loop with guidance_fn call ---
    {
        "name": "Main loop: inline APG/ADG → guidance_fn call",
        "marker": "guidance_fn(\n                            pred_cond, pred_null_cond",
        "pattern": (
            r"                    if apply_cfg_guidance:\n"
            r"                        if not use_adg:\n"
            r"                            vt = apg_forward\(\n"
            r"                                pred_cond=pred_cond,\n"
            r"                                pred_uncond=pred_null_cond,\n"
            r"                                guidance_scale=diffusion_guidance_sale,\n"
            r"                                momentum_buffer=momentum_buffer,\n"
            r"                                dims=\[1\],\n"
            r"                            \)\n"
            r"                        else:\n"
            r"                            vt = adg_forward\(\n"
            r"                                latents=xt,\n"
            r"                                noise_pred_cond=pred_cond,\n"
            r"                                noise_pred_uncond=pred_null_cond,\n"
            r"                                sigma=t_curr,\n"
            r"                                guidance_scale=diffusion_guidance_sale,\n"
            r"                            \)"
        ),
        "replacement": (
            "                    if apply_cfg_guidance:\n"
            "                        dt_val = (t_curr - t_prev) if isinstance(t_prev, (int, float)) else float(t_curr - t_prev)\n"
            "                        vt = guidance_fn(\n"
            "                            pred_cond, pred_null_cond, diffusion_guidance_sale,\n"
            "                            momentum_buffer=momentum_buffer,\n"
            "                            latents=xt, sigma=t_curr,\n"
            "                            dt=dt_val,\n"
            "                            step_idx=step_idx, total_steps=infer_steps,\n"
            "                        )"
        ),
    },
]


def find_checkpoint_model_files(checkpoints_dir: str):
    """Find all modeling_acestep_v15_base.py files in checkpoint directories."""
    results = []
    base_path = Path(checkpoints_dir)
    if not base_path.exists():
        return results
    for child in sorted(base_path.iterdir()):
        if child.is_dir():
            model_file = child / "modeling_acestep_v15_base.py"
            if model_file.exists():
                results.append(model_file)
    return results


def check_needs_solver_patch(content: str) -> bool:
    """Check if the file still has the original ODE/SDE/dpmsde inline blocks."""
    return "from acestep.core.generation.solvers import" not in content


def apply_patches(filepath: Path, dry_run: bool = False) -> dict:
    """Apply all patches to a single file. Returns patch report."""
    content = filepath.read_text(encoding="utf-8")
    original = content
    report = {"file": str(filepath), "patches": [], "skipped": [], "errors": []}

    for patch in PATCHES:
        name = patch["name"]
        marker = patch["marker"]
        pattern = patch["pattern"]
        replacement = patch["replacement"]

        # Check if already patched
        if marker in content:
            report["skipped"].append(name)
            continue

        # Try to apply
        new_content, count = re.subn(pattern, replacement, content, count=0)
        if count > 0:
            content = new_content
            report["patches"].append(f"{name} ({count} occurrence(s))")
        else:
            # Pattern not found — might be a different model version
            report["errors"].append(f"{name} — pattern not found (may be different model version)")

    if content != original and not dry_run:
        filepath.write_text(content, encoding="utf-8")

    report["modified"] = content != original
    return report


def main():
    parser = argparse.ArgumentParser(description="Patch checkpoint model files for solver/guidance registry")
    parser.add_argument(
        "--checkpoints-dir",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "checkpoints"),
        help="Path to checkpoints directory (default: ./checkpoints)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be patched without modifying files")
    args = parser.parse_args()

    print(f"Scanning: {args.checkpoints_dir}")
    if args.dry_run:
        print("DRY RUN — no files will be modified\n")

    files = find_checkpoint_model_files(args.checkpoints_dir)
    if not files:
        print("No modeling_acestep_v15_base.py files found in checkpoint directories.")
        return

    print(f"Found {len(files)} model file(s):\n")

    total_patched = 0
    total_skipped = 0

    for f in files:
        report = apply_patches(f, dry_run=args.dry_run)
        model_name = f.parent.name
        status = "MODIFIED" if report["modified"] else "UP TO DATE"
        print(f"  [{status}] {model_name}/")

        if report["patches"]:
            total_patched += 1
            for p in report["patches"]:
                print(f"    ✓ {p}")
        if report["skipped"]:
            for s in report["skipped"]:
                print(f"    · {s} (already applied)")
        if report["errors"]:
            for e in report["errors"]:
                print(f"    ⚠ {e}")
        print()

    total_ok = len(files) - total_patched
    print(f"Summary: {total_patched} patched, {total_ok} already up-to-date, {len(files)} total")


if __name__ == "__main__":
    main()
