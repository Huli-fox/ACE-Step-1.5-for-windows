"""Install audio-separator with diffq workaround for Python 3.13+/Windows.

Usage:
    python install_audio_separator.py

This script tries multiple install strategies for audio-separator,
which has a known build issue with its diffq-fixed dependency on
Windows + Python 3.13+.
"""

import shutil
import subprocess
import sys


def _find_uv() -> str:
    """Find the uv executable (may be in ~/.local/bin or on PATH)."""
    # Check PATH first
    uv = shutil.which("uv")
    if uv:
        return uv
    # Common install locations
    import pathlib
    for candidate in [
        pathlib.Path.home() / ".local" / "bin" / "uv",
        pathlib.Path.home() / ".local" / "bin" / "uv.exe",
    ]:
        if candidate.exists():
            return str(candidate)
    # Fallback: assume it's on PATH
    return "uv"


UV = _find_uv()


def _pip(*args: str, check: bool = True) -> int:
    cmd = [UV, "pip", *args]
    print(f"  > {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)
    if check and result.returncode != 0:
        raise RuntimeError(f"uv pip command failed: {' '.join(args)}")
    return result.returncode


def main():
    print("=" * 60)
    print("  Installing audio-separator for stem splitting")
    print("=" * 60)
    print()

    # ---- Strategy 1: Normal pip install ----
    print("[1/3] Trying normal pip install...")
    try:
        _pip("install", "audio-separator[gpu]>=0.30.0")
        print("  ✓ audio-separator installed successfully!")
        return
    except RuntimeError:
        print("  ✗ Normal install failed (likely diffq build error)")
        print()

    # ---- Strategy 2: Install diffq-fixed from source with Cython ----
    print("[2/3] Trying with Cython + diffq-fixed from source...")
    try:
        _pip("install", "Cython", check=False)
        _pip("install", "diffq-fixed", "--no-build-isolation")
        _pip("install", "audio-separator[gpu]>=0.30.0")
        print("  ✓ audio-separator installed with Cython workaround!")
        return
    except RuntimeError:
        print("  ✗ Cython workaround failed")
        print()

    # ---- Strategy 3: Install without diffq (stub it) ----
    print("[3/3] Installing audio-separator without diffq (CPU compression disabled)...")
    try:
        _pip("install", "audio-separator>=0.30.0", "--no-deps")
        # Install the deps we actually need (minus diffq)
        _pip("install", "torch", "torchaudio", "numpy", "scipy", "librosa",
             "soundfile", "onnxruntime", "requests", "tqdm", check=False)
        print("  ✓ audio-separator installed (without diffq — some models may not load)")
        print("    NOTE: Most models work fine without diffq. Only legacy compressed")
        print("    Demucs models require it.")
        return
    except RuntimeError:
        print("  ✗ All strategies failed!")
        print()
        print("  You can try installing manually:")
        print("    uv pip install audio-separator>=0.30.0")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
