"""Server-side stem separation service using audio_separator.

Models (lazy-downloaded on first use, ~1.8 GB total):
  - BS-RoFormer  for vocals/instrumental  (SDR 12.97)
  - htdemucs_6s  for 6-stem separation    (vocals, drums, bass, guitar, piano, other)

Two-pass pipeline (default, best quality):
  1. BS-RoFormer  → vocals (high quality) + instrumental
  2. htdemucs_6s  → instrumental → drums, bass, guitar, piano, other
  → Result: RoFormer vocals + 5 Demucs instrumental stems
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional
from uuid import uuid4

from loguru import logger


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class StemInfo:
    """Lightweight stem result descriptor."""

    __slots__ = ("id", "stem_type", "file_path", "file_name", "duration")

    def __init__(
        self,
        stem_type: str,
        file_path: str,
        file_name: str,
        duration: float = 0.0,
        id: Optional[str] = None,
    ):
        self.id = id or str(uuid4())
        self.stem_type = stem_type
        self.file_path = file_path
        self.file_name = file_name
        self.duration = duration

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "stem_type": self.stem_type,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "duration": self.duration,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_audio_duration(path: str) -> float:
    """Return duration in seconds (best-effort, returns 0.0 on failure)."""
    try:
        import soundfile as sf
        info = sf.info(path)
        return info.duration
    except Exception:
        pass
    try:
        import librosa
        dur = librosa.get_duration(path=path)
        return float(dur)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class StemService:
    """Singleton service for audio stem separation.

    Thread-safe lazy initialisation.  The underlying ``Separator``
    instance is created on first call and reused thereafter.
    """

    ROFORMER_MODEL = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
    DEMUCS_6S_MODEL = "htdemucs_6s.yaml"
    DEMUCS_FT_MODEL = "htdemucs_ft.yaml"

    def __init__(self, output_root: Optional[str] = None, device: str = "auto"):
        self._separator = None
        self._lock = threading.Lock()
        self._device = device
        # Default output root next to project dir
        if output_root is None:
            project_root = Path(__file__).resolve().parent.parent
            output_root = str(project_root / "stems_output")
        self._output_root = output_root
        os.makedirs(self._output_root, exist_ok=True)

    # ------------------------------------------------------------------
    # Lazy init
    # ------------------------------------------------------------------

    def _get_separator(self):
        """Lazy-init audio-separator."""
        if self._separator is None:
            with self._lock:
                if self._separator is None:
                    logger.info("[StemService] Loading audio-separator…")
                    from audio_separator.separator import Separator
                    self._separator = Separator()
                    logger.info("[StemService] audio-separator ready")
        return self._separator

    def is_available(self) -> bool:
        """Check whether audio_separator can be imported."""
        try:
            from audio_separator.separator import Separator  # noqa: F401
            return True
        except ImportError:
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def separate(
        self,
        audio_path: str,
        mode: str = "two-pass",
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> List[StemInfo]:
        """Separate *audio_path* into stems.

        Modes
        -----
        - ``vocals``   : BS-RoFormer → 2 stems (vocals + instrumental)
        - ``multi-4``  : htdemucs_ft → 4 stems (vocals, drums, bass, other)
        - ``multi-6``  : htdemucs_6s → 6 stems (vocals, drums, bass, guitar, piano, other)
        - ``two-pass`` : BS-RoFormer vocals, then htdemucs_6s on instrumental → 6+ stems
        """
        job_id = str(uuid4())
        output_dir = Path(self._output_root) / job_id
        output_dir.mkdir(parents=True, exist_ok=True)

        separator = self._get_separator()

        dispatch = {
            "vocals": self._separate_vocals,
            "multi-4": self._separate_multi_4,
            "multi-6": self._separate_multi_6,
            "two-pass": self._separate_two_pass,
        }
        handler = dispatch.get(mode)
        if handler is None:
            raise ValueError(f"Unknown stem mode: {mode!r}. "
                             f"Choose from: {', '.join(dispatch)}")

        return handler(separator, audio_path, output_dir, progress_callback)

    # ------------------------------------------------------------------
    # Internal separation strategies
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve(fpath: str, output_dir: Path) -> Path:
        p = Path(fpath)
        return p if p.is_absolute() else output_dir / p

    @staticmethod
    def _classify_stem_type(fname_lower: str, candidates: tuple) -> str:
        for c in candidates:
            if c in fname_lower:
                return c
        return "other"

    # ---- vocals only (RoFormer) ----

    def _separate_vocals(self, sep, audio_path, output_dir, cb) -> List[StemInfo]:
        if cb:
            cb("Loading BS-RoFormer model…", 0.1)

        sep.output_dir = str(output_dir)
        sep.output_format = "flac"
        sep.load_model(model_filename=self.ROFORMER_MODEL)

        if cb:
            cb("Separating vocals…", 0.3)

        files = sep.separate(audio_path)

        stems: List[StemInfo] = []
        for fp in files:
            fp = self._resolve(str(fp), output_dir)
            stem_type = "vocals" if "vocal" in fp.stem.lower() else "instrumental"
            stems.append(StemInfo(
                stem_type=stem_type,
                file_path=str(fp),
                file_name=fp.name,
                duration=_get_audio_duration(str(fp)),
            ))

        if cb:
            cb("Vocal separation complete", 1.0)
        return stems

    # ---- multi-4 (Demucs htdemucs_ft) ----

    def _separate_multi_4(self, sep, audio_path, output_dir, cb) -> List[StemInfo]:
        if cb:
            cb("Loading Demucs htdemucs_ft model…", 0.1)

        sep.output_dir = str(output_dir)
        sep.output_format = "flac"
        sep.load_model(model_filename=self.DEMUCS_FT_MODEL)

        if cb:
            cb("Separating stems (4-stem)…", 0.3)

        files = sep.separate(audio_path)

        stems: List[StemInfo] = []
        for fp in files:
            fp = self._resolve(str(fp), output_dir)
            stem_type = self._classify_stem_type(
                fp.stem.lower(), ("vocals", "drums", "bass", "other")
            )
            stems.append(StemInfo(
                stem_type=stem_type,
                file_path=str(fp),
                file_name=fp.name,
                duration=_get_audio_duration(str(fp)),
            ))
        if cb:
            cb("4-stem separation complete", 1.0)
        return stems

    # ---- multi-6 (Demucs htdemucs_6s) ----

    def _separate_multi_6(self, sep, audio_path, output_dir, cb) -> List[StemInfo]:
        if cb:
            cb("Loading Demucs htdemucs_6s model…", 0.1)

        sep.output_dir = str(output_dir)
        sep.output_format = "flac"
        sep.load_model(model_filename=self.DEMUCS_6S_MODEL)

        if cb:
            cb("Separating stems (6-stem)…", 0.3)

        files = sep.separate(audio_path)

        stems: List[StemInfo] = []
        for fp in files:
            fp = self._resolve(str(fp), output_dir)
            stem_type = self._classify_stem_type(
                fp.stem.lower(),
                ("vocals", "drums", "bass", "guitar", "piano", "other"),
            )
            stems.append(StemInfo(
                stem_type=stem_type,
                file_path=str(fp),
                file_name=fp.name,
                duration=_get_audio_duration(str(fp)),
            ))
        if cb:
            cb("6-stem separation complete", 1.0)
        return stems

    # ---- two-pass (RoFormer → htdemucs_6s) ----

    def _separate_two_pass(self, sep, audio_path, output_dir, cb) -> List[StemInfo]:
        # --- Pass 1: BS-RoFormer → vocals + instrumental ----
        if cb:
            cb("Pass 1/2: Isolating vocals with BS-RoFormer…", 0.05)

        sep.output_dir = str(output_dir)
        sep.output_format = "flac"
        sep.load_model(model_filename=self.ROFORMER_MODEL)

        if cb:
            cb("Pass 1/2: Separating…", 0.15)

        pass1_files = sep.separate(audio_path)

        vocals_path: Optional[str] = None
        instrumental_path: Optional[str] = None

        for fp in pass1_files:
            fp = str(self._resolve(str(fp), output_dir))
            fname = Path(fp).stem.lower()
            if "vocal" in fname and "instrument" not in fname:
                vocals_path = fp
            else:
                instrumental_path = fp

        if not instrumental_path:
            logger.warning("[StemService] Could not identify instrumental "
                           "from pass-1; falling back to vocals-only result")
            if cb:
                cb("Fallback: returning 2-stem result", 1.0)
            return self._separate_vocals(sep, audio_path, output_dir, cb)

        # --- Pass 2: htdemucs_6s on instrumental → 5 stems ----
        if cb:
            cb("Pass 2/2: Splitting instrumental with htdemucs_6s…", 0.45)

        pass2_dir = output_dir / "pass2"
        pass2_dir.mkdir(exist_ok=True)
        sep.output_dir = str(pass2_dir)
        sep.load_model(model_filename=self.DEMUCS_6S_MODEL)

        if cb:
            cb("Pass 2/2: Separating…", 0.55)

        pass2_files = sep.separate(instrumental_path)

        # --- Combine results ----
        stems: List[StemInfo] = []

        # Vocals from pass 1 (highest quality — RoFormer)
        if vocals_path:
            stems.append(StemInfo(
                stem_type="vocals",
                file_path=vocals_path,
                file_name=Path(vocals_path).name,
                duration=_get_audio_duration(vocals_path),
            ))

        # Instrumental stems from pass 2 (skip duplicate vocals from Demucs)
        for fp in pass2_files:
            fp = self._resolve(str(fp), pass2_dir)
            fname = fp.stem.lower()
            if "vocal" in fname:
                continue  # skip — we already have RoFormer vocals
            stem_type = self._classify_stem_type(
                fname, ("drums", "bass", "guitar", "piano", "other")
            )
            stems.append(StemInfo(
                stem_type=stem_type,
                file_path=str(fp),
                file_name=fp.name,
                duration=_get_audio_duration(str(fp)),
            ))

        if cb:
            cb("Two-pass separation complete", 1.0)
        return stems
