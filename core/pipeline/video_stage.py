"""
Stage 4: Video generation.

Produces a 1280×720 MP4 with:
  - Static dark background
  - Two speaker illustrations (left / right) — PNG files you provide in
    assets/. Falls back to clean placeholder rectangles if not present.
  - Optional logo in top-right corner (assets/logo.png)
  - Active speaker highlight: the speaking side brightens slightly each line
  - Dynamic subtitles: centered, per dialogue line, timed from the actual
    per-line TTS durations + assembly pause config (no guessing — derived
    from the same data the assembly stage used)
  - Animated waveform bar visualizer: reads actual audio samples per frame,
    computes short-window RMS, maps to bar heights

Architecture: renders frames with Pillow (full control over visual style),
pipes rawvideo bytes into ffmpeg (handles codec, muxing with audio). This
gives pixel-accurate rendering without needing MoviePy or any other
video-specific library.

Asset paths (relative to project root):
  assets/speaker_a.png   — left speaker illustration (optional)
  assets/speaker_b.png   — right speaker illustration (optional)
  assets/logo.png        — top-right logo (optional)

Video config lives in config.yaml under the `video:` key.
"""

import json
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont


# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------

W, H = 1280, 720
FPS = 30

# Visual layout
BG_COLOR = (26, 35, 50)            # dark blue-grey matching the reference image
SUBTITLE_COLOR = (255, 255, 255)    # white
SUBTITLE_SHADOW_COLOR = (0, 0, 0, 160)  # semi-transparent drop shadow
BAR_COLOR = (220, 220, 220)         # light grey bars, matches reference
BAR_COUNT = 40                      # number of waveform bars
BAR_MAX_HEIGHT = 80                 # pixels, max bar height
BAR_AREA_Y = int(H * 0.79)         # vertical center of bar area
BAR_AREA_W = 420                    # total width of bar cluster
SPEAKER_DIM_ALPHA = 160            # inactive speaker brightness (0-255)
SPEAKER_BRIGHT_ALPHA = 255         # active speaker brightness

# Font paths (DejaVu Sans Bold is always present on Ubuntu/Debian)
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

SUBTITLE_FONT_SIZE = 52
MAX_SUBTITLE_CHARS_PER_LINE = 48   # wrap at this width


# ---------------------------------------------------------------------------
# Timing derivation
# ---------------------------------------------------------------------------

def build_subtitle_timeline(
    lines: list[dict],
    tts_results: list[dict],
    skipped_indices: set,
    pause_between_turns_ms: int,
    pause_between_segments_ms: int,
) -> list[dict]:
    """
    Derives the exact start/end timestamp (in seconds) for each dialogue line
    in the final assembled audio, using the same logic as the assembly stage.

    Returns list of dicts: {line_index, speaker, text, segment_index,
                             start_sec, end_sec}
    """
    duration_by_index = {
        r["line_index"]: r.get("duration_seconds", 0.0)
        for r in tts_results
        if r.get("success") and r["line_index"] not in skipped_indices
    }

    timeline = []
    cursor = 0.0
    prev_segment = None

    for line in lines:
        idx = line["line_index"]
        if idx in skipped_indices or idx not in duration_by_index:
            continue

        # Insert pause (same logic as assembly_stage.py)
        if cursor > 0:
            if prev_segment is not None and line["segment_index"] != prev_segment:
                cursor += pause_between_segments_ms / 1000.0
            else:
                cursor += pause_between_turns_ms / 1000.0

        duration = duration_by_index[idx]
        timeline.append({
            "line_index": idx,
            "speaker": line["speaker"],
            "text": line["text"],
            "segment_index": line["segment_index"],
            "start_sec": cursor,
            "end_sec": cursor + duration,
        })
        cursor += duration
        prev_segment = line["segment_index"]

    return timeline


# ---------------------------------------------------------------------------
# Asset loading helpers
# ---------------------------------------------------------------------------

def _load_speaker_image(path: Path, target_w: int, target_h: int) -> Image.Image | None:
    """Load and resize a speaker illustration; return None if file missing."""
    if not path.exists():
        return None
    img = Image.open(path).convert("RGBA")
    img.thumbnail((target_w, target_h), Image.LANCZOS)
    return img


def _make_placeholder_speaker(w: int, h: int, color: tuple) -> Image.Image:
    """Simple colored rectangle as a fallback when no speaker image is provided."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([10, 10, w - 10, h - 10], radius=20, fill=color + (60,))
    return img


def _apply_alpha(img: Image.Image, alpha: int) -> Image.Image:
    """Return a copy of img with overall alpha multiplied by alpha/255."""
    r, g, b, a = img.split()
    a = a.point(lambda x: int(x * alpha / 255))
    return Image.merge("RGBA", (r, g, b, a))


# ---------------------------------------------------------------------------
# Per-frame rendering
# ---------------------------------------------------------------------------

def _wrap_text(text: str, max_chars: int) -> list[str]:
    """Simple word-wrap that keeps lines under max_chars."""
    words = text.split()
    lines, current = [], []
    for word in words:
        if sum(len(w) for w in current) + len(current) + len(word) > max_chars:
            if current:
                lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def _draw_subtitle(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont,
                   y_center: int, canvas_w: int):
    """Draw centered subtitle with a soft shadow for legibility."""
    lines = _wrap_text(text, MAX_SUBTITLE_CHARS_PER_LINE)
    line_h = font.size + 8
    total_h = line_h * len(lines)
    y = y_center - total_h // 2

    for line_text in lines:
        bbox = draw.textbbox((0, 0), line_text, font=font)
        tw = bbox[2] - bbox[0]
        x = (canvas_w - tw) // 2

        # Shadow
        draw.text((x + 2, y + 2), line_text, font=font, fill=(0, 0, 0, 160))
        # Main text
        draw.text((x, y), line_text, font=font, fill=SUBTITLE_COLOR)
        y += line_h


def _draw_waveform_bars(draw: ImageDraw.Draw, rms: float, canvas_w: int,
                         bar_y_center: int):
    """
    Draw a symmetric bar visualizer centered on canvas.
    rms: 0.0–1.0 normalized audio energy for this frame.
    Bars have slightly varied heights using a smooth envelope to look natural.
    """
    bar_total_w = BAR_AREA_W
    bar_w = 3
    gap = bar_total_w // BAR_COUNT - bar_w
    x_start = (canvas_w - bar_total_w) // 2

    # Smooth envelope across bars (taller in middle, shorter at edges)
    for i in range(BAR_COUNT):
        t = i / (BAR_COUNT - 1)  # 0 to 1
        envelope = np.sin(t * np.pi) ** 0.6  # smooth bell curve

        # Add slight asymmetric variation so bars aren't identical
        variation = 0.7 + 0.3 * abs(np.sin(i * 1.3))
        bar_h = max(2, int(BAR_MAX_HEIGHT * rms * envelope * variation))

        x = x_start + i * (bar_w + gap)
        y_top = bar_y_center - bar_h
        y_bot = bar_y_center + bar_h

        draw.rectangle([x, y_top, x + bar_w, y_bot], fill=BAR_COLOR)


class FrameRenderer:
    """Renders one video frame at a time, holding all static elements in memory."""

    def __init__(
        self,
        speaker_a_img: Image.Image | None,
        speaker_b_img: Image.Image | None,
        logo_img: Image.Image | None,
        subtitle_font: ImageFont.FreeTypeFont,
    ):
        self.speaker_a = speaker_a_img
        self.speaker_b = speaker_b_img
        self.logo = logo_img
        self.subtitle_font = subtitle_font

        # Pre-bake the static background (no text/bars) for fast per-frame copying
        self._static_bg = self._build_static_bg()

    def _build_static_bg(self) -> Image.Image:
        bg = Image.new("RGB", (W, H), BG_COLOR)
        # Speaker images are composited as part of the static bg since their
        # positions never change — only brightness changes per line, handled
        # separately by alpha-compositing dim/bright versions per frame.
        return bg

    def render(
        self,
        subtitle_text: str,
        active_speaker: str | None,
        rms: float,
    ) -> bytes:
        """
        Render one frame. Returns raw RGB bytes ready to pipe into ffmpeg.

        subtitle_text: text to show (empty string for silent gap frames)
        active_speaker: "A", "B", or None (gap/silence)
        rms: 0.0–1.0 normalized audio energy
        """
        frame = self._static_bg.copy().convert("RGBA")
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # --- Speaker illustrations ---
        spk_w, spk_h = 340, 420
        y_spk = H - spk_h - 10   # anchored to bottom

        for speaker_key, img, x_pos in [
            ("A", self.speaker_a, 0),
            ("B", self.speaker_b, W - spk_w),
        ]:
            if img is None:
                # Placeholder: subtle outline
                placeholder = _make_placeholder_speaker(spk_w, spk_h,
                    (80, 120, 160) if speaker_key == "A" else (160, 120, 80))
                alpha = SPEAKER_BRIGHT_ALPHA if active_speaker == speaker_key else SPEAKER_DIM_ALPHA
                placeholder = _apply_alpha(placeholder, alpha)
                overlay.paste(placeholder, (x_pos, y_spk), placeholder)
            else:
                resized = img.copy()
                if resized.size != (spk_w, spk_h):
                    resized.thumbnail((spk_w, spk_h), Image.LANCZOS)
                alpha = SPEAKER_BRIGHT_ALPHA if active_speaker == speaker_key else SPEAKER_DIM_ALPHA
                dimmed = _apply_alpha(resized, alpha)
                overlay.paste(dimmed, (x_pos, y_spk), dimmed)

        # --- Logo (top right) ---
        if self.logo:
            logo_w, logo_h = 140, 60
            logo_resized = self.logo.copy()
            logo_resized.thumbnail((logo_w, logo_h), Image.LANCZOS)
            overlay.paste(logo_resized, (W - logo_resized.width - 20, 15), logo_resized)

        # --- Waveform bars ---
        _draw_waveform_bars(draw, rms, W, BAR_AREA_Y)

        # --- Subtitle ---
        if subtitle_text:
            subtitle_y = int(H * 0.3)   # upper-center, clear of the speaker images
            _draw_subtitle(draw, subtitle_text, self.subtitle_font, subtitle_y, W)

        # Composite overlay onto frame
        frame = Image.alpha_composite(frame, overlay)
        return frame.convert("RGB").tobytes()


# ---------------------------------------------------------------------------
# Main stage function
# ---------------------------------------------------------------------------

def run_video_stage(
    job_dir: Path,
    lines: list[dict],
    tts_results: list[dict],
    assembly_config: dict,
    video_config: dict,
    log,
) -> Path:
    """
    Renders the full episode video.

    Reads:
        job_dir/04_final_audio.wav
        job_dir/02_script.json        (via `lines` argument)
        job_dir/03_tts_results.json   (via `tts_results` argument)
        job_dir/04_assembly_manifest.json

    Writes:
        job_dir/05_video.mp4

    Returns the path to the output video.
    """
    output_path = job_dir / "05_video.mp4"
    audio_path = job_dir / "04_final_audio.wav"
    manifest_path = job_dir / "04_assembly_manifest.json"

    if not audio_path.exists():
        raise FileNotFoundError(
            f"Final audio not found at {audio_path} — run assembly stage first."
        )

    with open(manifest_path) as f:
        manifest = json.load(f)
    skipped = set(manifest.get("skipped_line_indices", []))

    # ---- Load audio ----
    log.info("Loading audio for waveform extraction...")
    audio_data, audio_rate = sf.read(str(audio_path), dtype="float32")
    total_seconds = len(audio_data) / audio_rate
    total_frames = int(total_seconds * FPS) + 1
    samples_per_frame = audio_rate // FPS
    log.info(f"Audio: {total_seconds:.1f}s → {total_frames} frames @ {FPS}fps")

    # Precompute per-frame RMS values (fast — one pass over the whole file)
    rms_per_frame = []
    for fi in range(total_frames):
        start = fi * samples_per_frame
        end = start + samples_per_frame
        chunk = audio_data[start:end] if end <= len(audio_data) else audio_data[start:]
        if len(chunk) == 0:
            rms_per_frame.append(0.0)
        else:
            rms = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))
            rms_per_frame.append(rms)

    # Normalize RMS to 0–1 range against the 95th percentile (avoids clipping
    # on loud peaks while keeping typical speech energy well-represented)
    max_rms = np.percentile(rms_per_frame, 95) if max(rms_per_frame) > 0 else 1.0
    if max_rms == 0:
        max_rms = 1.0
    rms_per_frame = [min(r / max_rms, 1.0) for r in rms_per_frame]

    # ---- Build subtitle timeline ----
    timeline = build_subtitle_timeline(
        lines=lines,
        tts_results=tts_results,
        skipped_indices=skipped,
        pause_between_turns_ms=assembly_config.get("pause_between_turns_ms", 400),
        pause_between_segments_ms=assembly_config.get("pause_between_segments_ms", 900),
    )
    # Build a lookup: at any second offset, which line is active?
    # We'll scan frame-by-frame in the render loop instead for accuracy.

    # ---- Load assets ----
    project_root = job_dir.parent.parent  # jobs/{job_id}/ -> project root
    assets_dir = project_root / "assets"

    speaker_a_img = _load_speaker_image(assets_dir / "speaker_a.png", 340, 420)
    speaker_b_img = _load_speaker_image(assets_dir / "speaker_b.png", 340, 420)
    logo_img = _load_speaker_image(assets_dir / "logo.png", 180, 70)

    if speaker_a_img is None:
        log.info("assets/speaker_a.png not found — using placeholder. "
                 "Add a PNG to get your actual speaker illustration.")
    if speaker_b_img is None:
        log.info("assets/speaker_b.png not found — using placeholder.")

    subtitle_font_size = video_config.get("subtitle_font_size", SUBTITLE_FONT_SIZE)
    font_path = video_config.get("font_path", FONT_BOLD)
    subtitle_font = ImageFont.truetype(font_path, subtitle_font_size)

    renderer = FrameRenderer(speaker_a_img, speaker_b_img, logo_img, subtitle_font)

    # ---- Spin up ffmpeg process ----
    # Receives raw RGB frames via stdin, muxes with audio, outputs MP4.
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        # Video input from stdin (raw RGB frames)
        "-f", "rawvideo",
        "-pixel_format", "rgb24",
        "-video_size", f"{W}x{H}",
        "-framerate", str(FPS),
        "-i", "pipe:0",
        # Audio input
        "-i", str(audio_path),
        # Encoding
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", str(video_config.get("crf", 23)),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(output_path),
    ]

    log.info(f"Starting ffmpeg render: {total_frames} frames, {total_seconds:.1f}s...")
    ffmpeg_proc = subprocess.Popen(
        ffmpeg_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    # ---- Render frame by frame ----
    timeline_idx = 0  # pointer into the timeline list
    log_interval = max(1, total_frames // 10)

    try:
        for fi in range(total_frames):
            t = fi / FPS  # current time in seconds

            # Advance timeline pointer to the active subtitle entry
            while (timeline_idx + 1 < len(timeline) and
                   timeline[timeline_idx + 1]["start_sec"] <= t):
                timeline_idx += 1

            # Determine what's active at this frame
            active_entry = None
            if timeline and timeline[timeline_idx]["start_sec"] <= t <= timeline[timeline_idx]["end_sec"]:
                active_entry = timeline[timeline_idx]

            subtitle_text = active_entry["text"] if active_entry else ""
            active_speaker = active_entry["speaker"] if active_entry else None
            rms = rms_per_frame[fi] if fi < len(rms_per_frame) else 0.0

            frame_bytes = renderer.render(subtitle_text, active_speaker, rms)
            ffmpeg_proc.stdin.write(frame_bytes)

            if fi % log_interval == 0:
                pct = fi / total_frames * 100
                log.info(f"  Video render: {fi}/{total_frames} frames ({pct:.0f}%)")

        # communicate() closes stdin for us before waiting — don't close manually
        _, stderr = ffmpeg_proc.communicate(timeout=120)

        if ffmpeg_proc.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed (exit {ffmpeg_proc.returncode}):\n"
                f"{stderr.decode(errors='replace')[-2000:]}"
            )

    except Exception:
        if not ffmpeg_proc.stdin.closed:
            ffmpeg_proc.stdin.close()
        ffmpeg_proc.wait()
        raise

    log.info(f"Video stage complete: {output_path} ({total_seconds:.1f}s)")
    return output_path
