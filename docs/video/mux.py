#!/usr/bin/env python3
"""Mux the clean AdWatch voice-over onto a screen recording.

    python3 mux.py recording.mov adwatch_vo_3min.mp3 --offset 5.85 -o adwatch_demo.mp4
    python3 mux.py recording.mov adwatch_vo_3min.mp3 --auto        -o adwatch_demo.mp4

--offset  seconds from the start of the recording to where the clean track should start.
          If you played the *_GUIDE.mp3 from the first frame of the recording, that is 5.85.
--auto    the recording has a mic track that picked up the GUIDE track playing on speakers:
          cross-correlate it with the clean track to find the offset (needs numpy).

Output: 1080p (letterboxed if needed) H.264 30 fps + AAC 160k, faststart, trimmed to narration + 1 s.
Requires ffmpeg on PATH.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


def sh(*cmd: str, capture: bool = True) -> str:
    r = subprocess.run(cmd, check=True, capture_output=capture, text=True)
    return r.stdout if capture else ""


def duration(p: Path) -> float:
    return float(sh("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)).strip())


def has_audio(p: Path) -> bool:
    return "audio" in sh("ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(p))


def auto_offset(rec: Path, vo: Path) -> float:
    import numpy as np  # noqa: PLC0415

    sr = 8000
    with tempfile.TemporaryDirectory() as td:
        a, b = Path(td, "rec.raw"), Path(td, "vo.raw")
        for src, dst in ((rec, a), (vo, b)):
            sh("ffmpeg", "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", str(dst))
        x = np.frombuffer(a.read_bytes(), dtype=np.int16).astype(np.float32)
        y = np.frombuffer(b.read_bytes(), dtype=np.int16).astype(np.float32)
    # envelope correlation is robust to speaker/mic coloration
    def env(s: np.ndarray, win: int = 400) -> np.ndarray:
        s = np.abs(s)
        c = np.cumsum(np.insert(s, 0, 0))
        e = (c[win:] - c[:-win]) / win
        return (e - e.mean()) / (e.std() + 1e-9)

    ex, ey = env(x), env(y[: sr * 60])  # first 60 s of the clean track is plenty
    n = len(ex) + len(ey) - 1
    corr = np.fft.irfft(np.fft.rfft(ex, n) * np.conj(np.fft.rfft(ey, n)), n)
    lag = int(np.argmax(corr[: len(ex)]))
    return lag / sr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("recording")
    ap.add_argument("voiceover")
    ap.add_argument("-o", "--out", default="adwatch_demo.mp4")
    ap.add_argument("--offset", type=float, default=None, help="seconds into the recording where the clean track starts")
    ap.add_argument("--auto", action="store_true", help="find the offset from the recording's mic track")
    ap.add_argument("--fps", type=int, default=30)
    a = ap.parse_args()
    rec, vo, out = Path(a.recording), Path(a.voiceover), Path(a.out)

    if a.auto:
        if not has_audio(rec):
            print("recording has no audio track; use --offset", file=sys.stderr)
            return 2
        off = auto_offset(rec, vo)
        print(f"auto offset: {off:.2f}s")
    elif a.offset is not None:
        off = a.offset
    else:
        off = 0.0
        print("no --offset/--auto given; assuming the clean track starts at frame 0")

    vo_len = duration(vo)
    total = vo_len + 1.0
    rec_len = duration(rec)
    if off + total > rec_len + 0.5:
        print(f"warning: recording is {rec_len:.1f}s but needs {off + total:.1f}s; the tail will be frozen on the last frame", file=sys.stderr)

    vf = f"fps={a.fps},scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p,tpad=stop_mode=clone:stop_duration=5"
    sh(
        "ffmpeg", "-y", "-v", "error",
        "-ss", f"{off:.3f}", "-i", str(rec),
        "-i", str(vo),
        "-map", "0:v:0", "-map", "1:a:0",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
        "-t", f"{total:.3f}", "-movflags", "+faststart",
        str(out), capture=False,
    )
    print(f"wrote {out} ({duration(out):.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
