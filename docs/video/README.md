# AdWatch demo video — voice-over + assembly

Digital narration of `docs/VIDEO_SCRIPT.md`, voice **en-US-AndrewNeural** (Microsoft neural TTS via `edge-tts`), rate +4%, loudness-normalized to −16 LUFS / −1.5 dBTP (YouTube/Devpost safe). Mono 44.1 kHz, 128 kbps MP3.

| File | Runtime | Use |
|---|---|---|
| `adwatch_vo_3min.mp3` | **2:59** | **Default for Devpost.** The script's "3:00 flat" cut: row 3a dropped, 8d shortened to the tagline, 2b click-pause 2 s, 4 s hold after "Here is one." |
| `adwatch_vo_full.mp3` | 3:20 | Every row as written (timecodes match the script within ±2 s). Use if the platform has no 3-minute cap. |
| `adwatch_vo_2min.mp3` | 2:08 | The script's 2:00 cut (rows 1a, 3a, 3b, 5b, 6c, 7, 8d dropped). Both sponsor beats survive. |
| `adwatch_vo_3min_GUIDE.mp3` / `_full_GUIDE.mp3` | +5.9 s | Same track with a spoken "three, two, one" + beep in front. **Play this one while you record** so you know when narration starts. Not for the final video. |
| `*_cues.csv` | — | Per row: start/end time, what must be on screen, narration. Open next to the recorder. |
| `clips.zip` | — | Per-row clips `clips/<row>.mp3` (+ `8d_short`) and the three voice samples (Andrew / Brian / Ava). Re-cut without re-synthesizing. |

Note on row **5b**: the track says "Here is one." and then holds (4 s in the 3-min cut, 8 s in full) while the cursor sits on the first action box and the evidence panel opens. The viewer reads the box. If you'd rather have it spoken, paste the box's text and it gets synthesized into the clip.

## Recording workflow (screen only, no mic needed)

1. Pre-flight per `VIDEO_SCRIPT.md` (own account, tabs pre-loaded, warm Collect now ~10 min before, DND on, 1920×1080).
2. Open `adwatch_vo_3min_cues.csv` on a second screen or phone.
3. **Cmd+Shift+5 → Record Selected Portion** (or Entire Screen) → Options: **Microphone: on** (any mic — it is only used to sync, then discarded), timer 5 s. Start.
4. Play `adwatch_vo_3min_GUIDE.mp3` **through speakers** (Finder space-bar preview is fine). Follow the cues: cursor on the stat cards at "This is AdWatch", scroll at "That is a snapshot", etc. Don't move the mouse during 6b.
5. Stop after the tagline. Drop the `.mov` into `docs/video/` and say so — the mic audio is cross-correlated against the clean track to find the offset, then replaced with the clean track, and exported as 1080p H.264/AAC MP4 (`mux.py`).

Fallback if you record without a mic: start the screen recording, then start the GUIDE track, and write down the number of seconds between the two (or just leave the first frame of the recording on the desktop and switch to the browser at the beep — the switch is the sync point).

## Assembling yourself (optional)

```bash
python3 docs/video/mux.py recording.mov docs/video/adwatch_vo_3min.mp3 --offset 5.85 -o adwatch_demo.mp4
#   --offset = seconds from the start of the recording to the start of the clean track
#              (with the GUIDE track played from t=0 of the recording that is 5.85 s)
#   --auto   = find the offset by cross-correlating the recording's mic track instead
```

Needs `ffmpeg` (and `numpy` for `--auto`). Output: H.264 1080p 30 fps, AAC 160 kbps, faststart, trimmed to the narration length + 1 s.
