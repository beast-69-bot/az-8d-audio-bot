"""
Core Audio & Video Engine for AZ 8D Audio Bot.
"""

import os
import sys
import time
import shutil
import threading
import subprocess
import numpy as np
import scipy.io.wavfile as wav
import scipy.signal as signal
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from config import (
    AUDIO_SAMPLE_RATE, MP3_BITRATE, TARGET_LUFS, TARGET_TP, TEMP_DIR, ASSETS_DIR
)
from processor import PRESETS, process_8d_dsp, simple_schroeder_reverb

VISUALIZER_STYLES = {
    "style1_smooth_wave": {
        "name": "〰️ Smooth Center Wave",
        "desc": "Minimalist white glowing liquid wave behind card",
        "filter": "[1:a]showwaves=s=1440x360:mode=cline:colors=white@0.9:scale=cbrt,format=yuva420p[vis]; [bg][vis]overlay=(W-w)/2:(H-h)/2[stage1]; [stage1][art]overlay=(W-w)/2:(H-h)/2[v]"
    },
    "style2_spectrum_bars": {
        "name": "📊 Spectrum Equalizer Bars",
        "desc": "Dynamic logarithmic DJ frequency bars behind card",
        "filter": "[1:a]showfreqs=s=1440x380:mode=bar:fscale=log:ascale=cbrt:colors=0x38bdf8@0.9,format=yuva420p[vis]; [bg][vis]overlay=(W-w)/2:(H-h)/2+50[stage1]; [stage1][art]overlay=(W-w)/2:(H-h)/2[v]"
    },
    "style3_mirrored_dual": {
        "name": "🪞 Mirrored Dual Frequency",
        "desc": "Symmetric top-bottom blue frequency wave",
        "filter": "[1:a]showwaves=s=1440x440:mode=p2p:colors=0x38bdf8@0.9:scale=sqrt,format=yuva420p[vis]; [bg][vis]overlay=(W-w)/2:(H-h)/2[stage1]; [stage1][art]overlay=(W-w)/2:(H-h)/2[v]"
    },
    "style4_neon_gradient": {
        "name": "🌈 Neon Cyber Glow",
        "desc": "Cyan to Rose Pink color-shifting wave",
        "filter": "[1:a]showwaves=s=1440x360:mode=cline:colors=0x00f5ff|0xf43f5e:scale=cbrt,format=yuva420p[vis]; [bg][vis]overlay=(W-w)/2:(H-h)/2[stage1]; [stage1][art]overlay=(W-w)/2:(H-h)/2[v]"
    },
    "style5_stereo_scope": {
        "name": "🌀 3D Stereo Orbit Scope",
        "desc": "Real-time circular scope that tracks 8D rotation around card",
        "filter": "[1:a]avectorscope=s=920x920:m=lissajous:draw=line:scale=sqrt:rc=0:gc=245:bc=255:rf=0:gf=200:bf=255,format=yuva420p[vis]; [bg][vis]overlay=(W-w)/2:(H-h)/2[stage1]; [stage1][art]overlay=(W-w)/2:(H-h)/2[v]"
    }
}

def extract_metadata_and_cover(input_audio: str, out_cover_path: str) -> Dict[str, Any]:
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        input_audio
    ]
    meta = {"title": "Unknown Title", "artist": "Unknown Artist", "duration": 0.0, "has_cover": False}
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        import json
        data = json.loads(res.stdout)
        fmt = data.get("format", {})
        tags = fmt.get("tags", {})
        meta["title"] = tags.get("title", tags.get("TITLE", Path(input_audio).stem))
        meta["artist"] = tags.get("artist", tags.get("ARTIST", "Unknown Artist"))
        meta["duration"] = float(fmt.get("duration", 0.0))
        for st in data.get("streams", []):
            if st.get("codec_type") == "video":
                meta["has_cover"] = True
                break
    except Exception as e:
        meta["title"] = Path(input_audio).stem

    if meta["has_cover"]:
        cmd_extract = [
            "ffmpeg", "-y",
            "-i", input_audio,
            "-an", "-vcodec", "copy",
            out_cover_path
        ]
        try:
            subprocess.run(cmd_extract, capture_output=True, check=True)
        except:
            meta["has_cover"] = False

    return meta

def extract_audio_from_video(video_path: str, output_mp3: str, out_cover_path: Optional[str] = None, progress_callback=None) -> Dict[str, Any]:
    """
    Extracts high-bitrate 320 kbps MP3 audio stream from any video file
    and extracts a clean representative frame snapshot as album cover artwork.
    """
    if progress_callback:
        progress_callback(30, "Extracting 320 kbps audio stream from video...")

    cmd_extract = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-c:a", "libmp3lame",
        "-b:a", MP3_BITRATE,
        "-ar", str(AUDIO_SAMPLE_RATE),
        output_mp3
    ]
    subprocess.run(cmd_extract, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    has_cover = False
    if out_cover_path:
        if progress_callback:
            progress_callback(70, "Extracting video thumbnail for cover art...")
        cmd_thumb = [
            "ffmpeg", "-y",
            "-ss", "00:00:02",
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            out_cover_path
        ]
        try:
            res = subprocess.run(cmd_thumb, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0 and os.path.exists(out_cover_path) and os.path.getsize(out_cover_path) > 0:
                has_cover = True
            else:
                # Fallback to first frame if video is shorter than 2s
                cmd_thumb_fallback = [
                    "ffmpeg", "-y",
                    "-i", video_path,
                    "-vframes", "1",
                    "-q:v", "2",
                    out_cover_path
                ]
                subprocess.run(cmd_thumb_fallback, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(out_cover_path) and os.path.getsize(out_cover_path) > 0:
                    has_cover = True
        except Exception:
            has_cover = False

    meta = extract_metadata_and_cover(output_mp3, out_cover_path or "")
    if has_cover:
        meta["has_cover"] = True

    if progress_callback:
        progress_callback(100, "Audio extracted successfully!")

    return meta

def remove_vocals_dsp(input_audio: str, output_mp3: str, progress_callback=None) -> str:
    """
    Fast center-channel vocal cancellation DSP.
    Isolates sub-bass (<130Hz) and air (>7.5kHz), while applying mid-side phase cancellation
    to the vocal presence band (130Hz-7.5kHz). Mastered at -14 LUFS 320kbps.
    """
    if progress_callback:
        progress_callback(30, "Isolating stereo side instruments & cancelling center vocals...")

    filter_complex = (
        "[0:a]lowpass=f=130[bass]; "
        "[0:a]highpass=f=7500[air]; "
        "[0:a]bandpass=f=1800:width_type=h:w=3500,pan=stereo|c0=c0-c1|c1=c1-c0[karaoke]; "
        "[bass][karaoke]amix=inputs=2:weights=1.2 1.0[mid]; "
        "[mid][air]amix=inputs=2:weights=1.0 0.8,loudnorm=I=-14:TP=-1.0[out]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", input_audio,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-c:a", "libmp3lame",
        "-b:a", MP3_BITRATE,
        output_mp3
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if progress_callback:
        progress_callback(100, "Vocal removal complete!")
    return output_mp3

def remove_vocals_ai(input_audio: str, output_mp3: str, temp_dir: Optional[str] = None, progress_callback=None) -> str:
    """
    Meta Demucs AI Neural Network vocal remover.
    Separates song into vocals and accompaniment (instrumental/karaoke) with studio quality.
    """
    if progress_callback:
        progress_callback(20, "Starting Meta Demucs AI Neural Network...")

    out_dir = Path(temp_dir or TEMP_DIR) / f"demucs_{int(time.time())}"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    cmd_demucs = [
        sys.executable, "-m", "demucs.separate",
        "-n", "htdemucs",
        "--two-stems", "vocals",
        "-d", "cpu",
        "-j", "4",
        "--mp3",
        "--mp3-bitrate", "320",
        "-o", str(out_dir),
        input_audio
    ]
    
    stop_ticker = threading.Event()
    def progress_ticker():
        stages = [
            (35, "Neural layers analyzing vocal harmonics..."),
            (50, "Separating lead and backing vocals..."),
            (65, "Isolating stereo instrumental accompaniment..."),
            (78, "Extracting clean instrumental track..."),
        ]
        for pct, desc in stages:
            if stop_ticker.wait(7):
                break
            if progress_callback:
                progress_callback(pct, desc)

    ticker_thread = threading.Thread(target=progress_ticker, daemon=True)
    ticker_thread.start()

    try:
        subprocess.run(cmd_demucs, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        stop_ticker.set()
        
        matches = list(out_dir.rglob("no_vocals.mp3"))
        if not matches:
            matches = list(out_dir.rglob("no_vocals.wav"))
            
        if not matches:
            raise RuntimeError("Demucs failed to produce no_vocals stem")
            
        no_vocals_file = matches[0]
        
        if progress_callback:
            progress_callback(88, "Mastering AI Instrumental to 320 kbps MP3...")

        cmd_master = [
            "ffmpeg", "-y",
            "-i", str(no_vocals_file),
            "-c:a", "libmp3lame",
            "-b:a", MP3_BITRATE,
            "-filter:a", f"loudnorm=I={TARGET_LUFS}:TP={TARGET_TP}",
            output_mp3
        ]
        subprocess.run(cmd_master, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if progress_callback:
            progress_callback(100, "AI Vocal removal complete!")
        return output_mp3
    finally:
        stop_ticker.set()
        if out_dir.exists():
            try:
                shutil.rmtree(out_dir, ignore_errors=True)
            except Exception:
                pass

def process_16d_dsp(input_wav: str, output_wav: str):
    sr, data = wav.read(input_wav)
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    else:
        data = data.astype(np.float32)
        
    mono = (data[:, 0] + data[:, 1]) * 0.5
    n = len(mono)
    t = np.linspace(0, n / sr, n, endpoint=False)
    
    # 1. Sub-bass anchor (<110Hz)
    sos_lp = signal.butter(2, 110.0, 'low', fs=sr, output='sos')
    sub = signal.sosfilt(sos_lp, signal.sosfilt(sos_lp, mono))
    
    # 2. Mid band (110Hz - 2500Hz)
    sos_bp = signal.butter(2, [110.0, 2500.0], 'bandpass', fs=sr, output='sos')
    mid = signal.sosfilt(sos_bp, mono)
    
    # 3. High band (>2500Hz)
    sos_hp = signal.butter(2, 2500.0, 'high', fs=sr, output='sos')
    high = signal.sosfilt(sos_hp, mono)
    
    # Orbit 1: Clockwise 12s
    omega_mid = 2.0 * np.pi / 12.0
    pan_mid = np.sin(omega_mid * t)
    gain_mid_l = np.cos((pan_mid + 1.0) * (np.pi / 4.0)) * 0.85 + 0.15 * 0.707
    gain_mid_r = np.sin((pan_mid + 1.0) * (np.pi / 4.0)) * 0.85 + 0.15 * 0.707
    
    # Orbit 2: Counter-clockwise 8s
    omega_high = -2.0 * np.pi / 8.0
    pan_high = np.sin(omega_high * t)
    gain_high_l = np.cos((pan_high + 1.0) * (np.pi / 4.0)) * 0.90 + 0.10 * 0.707
    gain_high_r = np.sin((pan_high + 1.0) * (np.pi / 4.0)) * 0.90 + 0.10 * 0.707
    
    rev_l, rev_r = simple_schroeder_reverb(mid + high, sr, wet=0.14, decay=1.4)
    out_l = sub + (mid * gain_mid_l) + (high * gain_high_l) + rev_l
    out_r = sub + (mid * gain_mid_r) + (high * gain_high_r) + rev_r
    
    peak = max(np.max(np.abs(out_l)), np.max(np.abs(out_r)))
    if peak > 0.95:
        out_l = np.tanh(out_l / peak) * 0.95
        out_r = np.tanh(out_r / peak) * 0.95
        
    stereo = np.vstack([out_l, out_r]).T
    wav.write(output_wav, sr, (stereo * 32767).astype(np.int16))

def process_audio_effect(input_audio: str, output_mp3: str, effect: str = "8d", progress_callback=None) -> str:
    if effect == "vocal_dsp":
        return remove_vocals_dsp(input_audio, output_mp3, progress_callback=progress_callback)
    elif effect == "vocal_ai":
        return remove_vocals_ai(input_audio, output_mp3, progress_callback=progress_callback)

    temp_wav_in = str(TEMP_DIR / f"temp_in_{int(time.time()*1000)}.wav")
    temp_wav_proc = str(TEMP_DIR / f"temp_proc_{int(time.time()*1000)}.wav")
    
    if progress_callback:
        progress_callback(15, "Decoding audio to 48kHz PCM...")
        
    cmd_dec = ["ffmpeg", "-y", "-i", input_audio, "-vn", "-ar", str(AUDIO_SAMPLE_RATE), "-ac", "2", temp_wav_in]
    subprocess.run(cmd_dec, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if progress_callback:
        progress_callback(40, f"Applying {effect.upper()} psychoacoustic spatial DSP...")
        
    if effect == "8d":
        process_8d_dsp(temp_wav_in, temp_wav_proc, PRESETS["standard"], boost_bass=False)
    elif effect == "8d_bass":
        process_8d_dsp(temp_wav_in, temp_wav_proc, PRESETS["standard"], boost_bass=True)
    elif effect == "16d":
        process_16d_dsp(temp_wav_in, temp_wav_proc)
    elif effect == "slowed":
        cmd_eff = [
            "ffmpeg", "-y", "-i", temp_wav_in,
            "-filter_complex", "asetrate=48000*0.85,aresample=48000,lowpass=f=9000,aecho=0.8:0.7:60|90:0.35|0.25",
            temp_wav_proc
        ]
        subprocess.run(cmd_eff, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif effect == "sped_up":
        cmd_eff = [
            "ffmpeg", "-y", "-i", temp_wav_in,
            "-filter_complex", "asetrate=48000*1.20,aresample=48000,treble=g=2:f=4000",
            temp_wav_proc
        ]
        subprocess.run(cmd_eff, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif effect == "bass_boost":
        cmd_eff = [
            "ffmpeg", "-y", "-i", temp_wav_in,
            "-filter_complex", "bass=g=7:f=65:w=0.6,compand=attacks=0.02:decays=0.1:points=-80/-80|-15/-15|0/-1",
            temp_wav_proc
        ]
        subprocess.run(cmd_eff, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        process_8d_dsp(temp_wav_in, temp_wav_proc, PRESETS["standard"], boost_bass=False)

    if progress_callback:
        progress_callback(80, "Mastering via EBU R128 (-14 LUFS) @ 320kbps...")

    cmd_master = [
        "ffmpeg", "-y",
        "-i", temp_wav_proc,
        "-i", input_audio,
        "-map", "0:a",
        "-map", "1:v?",
        "-c:a", "libmp3lame",
        "-b:a", MP3_BITRATE,
        "-c:v", "copy",
        "-id3v2_version", "3",
        "-metadata", f"album=8D Remaster ({effect.upper()})",
        "-filter:a", f"loudnorm=I={TARGET_LUFS}:LRA=7:TP={TARGET_TP}:dual_mono=false",
        output_mp3
    ]
    subprocess.run(cmd_master, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    for p in [temp_wav_in, temp_wav_proc]:
        if os.path.exists(p):
            try:
                os.remove(p)
            except:
                pass
                
    if progress_callback:
        progress_callback(100, "Audio processing complete!")
        
    return output_mp3

def render_visualizer_video(
    audio_path: str,
    image_path: str,
    output_mp4: str,
    style_key: str = "style1_smooth_wave",
    total_duration: float = 0.0,
    progress_callback=None
) -> str:
    style_info = VISUALIZER_STYLES.get(style_key, VISUALIZER_STYLES["style1_smooth_wave"])
    
    filter_complex = (
        f"[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,boxblur=20:2,eq=brightness=-0.08:contrast=1.05[bg]; "
        f"[0:v]scale=620:620,pad=628:628:4:4:color=white@0.35[art]; "
        f"{style_info['filter']}"
    )
    
    cmd_render = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", image_path,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-tune", "stillimage",
        "-crf", "26",
        "-maxrate", "1600k",
        "-bufsize", "3000k",
        "-r", "24",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-shortest",
        "-progress", "pipe:1",
        "-nostats",
        output_mp4
    ]
    
    process = subprocess.Popen(cmd_render, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    last_update = 0.0
    
    for line in process.stdout:
        line = line.strip()
        if line.startswith("out_time_us="):
            try:
                us = int(line.split("=")[1])
                curr_sec = us / 1000000.0
                if total_duration > 0 and progress_callback:
                    now = time.time()
                    if now - last_update >= 2.0:
                        pct = min(98.0, max(5.0, (curr_sec / total_duration) * 100.0))
                        progress_callback(pct, f"Rendering frame ({curr_sec:.1f}s / {total_duration:.1f}s)")
                        last_update = now
            except:
                pass
        elif line == "progress=end":
            if progress_callback:
                progress_callback(100.0, "Render complete!")
                
    process.wait()
    if process.returncode != 0:
        raise RuntimeError("FFmpeg video rendering failed!")
        
    return output_mp4
