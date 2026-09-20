"""
Psychoacoustic DSP Engine for 8D Spatial Audio.
Implements:
1. Linkwitz-Riley 4th-Order Crossover (Sub-Bass Anchored Mono)
2. Continuous 360-Degree Circular Orbit Trajectory
3. Fractional-Delay Interaural Time Difference (ITD <= 650us)
4. Interaural Level Difference (ILD) with Head Shadow & Distance Decay
5. Dynamic Pinna Shadow Filter (Rear High-Shelf Damping > 4.5kHz)
6. Diffuse Algorithmic Reverberator with Abbey Road Filtering
7. Tanh Soft Peak Limiting
"""

import numpy as np
import scipy.io.wavfile as wav
import scipy.signal as signal
from dataclasses import dataclass

SPEED_OF_SOUND = 343.0 # m/s
HEAD_RADIUS = 0.0875   # ~17.5 cm interaural distance (KEMAR standard)

@dataclass
class Preset8D:
    name: str
    rotation_period: float
    orbit_radius: float
    crossfeed_min: float
    pinna_rear_damping_db: float
    reverb_wet: float
    reverb_decay: float
    bass_crossover_hz: float

PRESETS = {
    "soft": Preset8D(
        name="Soft 8D",
        rotation_period=16.0,
        orbit_radius=1.8,
        crossfeed_min=0.28,
        pinna_rear_damping_db=2.5,
        reverb_wet=0.08,
        reverb_decay=0.8,
        bass_crossover_hz=120.0
    ),
    "standard": Preset8D(
        name="Standard 8D",
        rotation_period=10.0,
        orbit_radius=1.5,
        crossfeed_min=0.15,
        pinna_rear_damping_db=4.5,
        reverb_wet=0.15,
        reverb_decay=1.3,
        bass_crossover_hz=110.0
    ),
    "immersive": Preset8D(
        name="Immersive 8D",
        rotation_period=8.0,
        orbit_radius=1.2,
        crossfeed_min=0.08,
        pinna_rear_damping_db=6.5,
        reverb_wet=0.22,
        reverb_decay=1.8,
        bass_crossover_hz=100.0
    )
}

def fractional_delay(signal_in, delay_samples):
    n_samples = len(signal_in)
    indices = np.arange(n_samples) - delay_samples
    valid_mask = (indices >= 0) & (indices < n_samples - 1)
    idx_floor = np.floor(indices).astype(int)
    frac = indices - idx_floor
    out = np.zeros(n_samples, dtype=np.float32)
    valid_idx = np.where(valid_mask)[0]
    vf = idx_floor[valid_idx]
    out[valid_idx] = (1.0 - frac[valid_idx]) * signal_in[vf] + frac[valid_idx] * signal_in[vf + 1]
    return out

def simple_schroeder_reverb(mono_signal, sr, wet=0.15, decay=1.2):
    comb_delays = [int(sr * d) for d in [0.0297, 0.0371, 0.0411, 0.0437]]
    comb_gains = [10.0 ** (-3.0 * (cd / sr) / decay) for cd in comb_delays]
    comb_outputs = []
    for d, g in zip(comb_delays, comb_gains):
        b = np.zeros(d + 1)
        b[d] = 1.0
        a = np.zeros(d + 1)
        a[0] = 1.0
        a[d] = -g
        comb_out = signal.lfilter(b, a, mono_signal)
        comb_outputs.append(comb_out)
    comb_sum = sum(comb_outputs) * 0.25
    ap_delays = [int(sr * 0.005), int(sr * 0.0017)]
    ap_gain = 0.5
    ap_out = comb_sum
    for ap_d in ap_delays:
        b_ap = np.zeros(ap_d + 1)
        b_ap[0] = -ap_gain
        b_ap[ap_d] = 1.0
        a_ap = np.zeros(ap_d + 1)
        a_ap[0] = 1.0
        a_ap[ap_d] = -ap_gain
        ap_out = signal.lfilter(b_ap, a_ap, ap_out)
    sos_hp = signal.butter(2, 300.0, 'hp', fs=sr, output='sos')
    sos_lp = signal.butter(2, 6500.0, 'lp', fs=sr, output='sos')
    rev_clean = signal.sosfilt(sos_lp, signal.sosfilt(sos_hp, ap_out))
    r_delay_samples = int(sr * 0.012)
    rev_l = rev_clean
    rev_r = np.pad(rev_clean, (r_delay_samples, 0))[:len(rev_clean)]
    return rev_l * wet, rev_r * wet

def process_8d_dsp(input_wav_path, output_wav_path, preset: Preset8D, boost_bass: bool = False):
    sr, data = wav.read(input_wav_path)
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0
    else:
        data = data.astype(np.float32)
        
    if len(data.shape) == 1:
        mono = data
        left_orig, right_orig = data, data
    else:
        left_orig, right_orig = data[:, 0], data[:, 1]
        mono = (left_orig + right_orig) * 0.5
        
    n_samples = len(mono)
    t = np.linspace(0, n_samples / sr, n_samples, endpoint=False)
    
    # 1. Anchored Sub-Bass Split (4th Order Linkwitz-Riley)
    sos_lp = signal.butter(2, preset.bass_crossover_hz, 'low', fs=sr, output='sos')
    sub_bass_mono = signal.sosfilt(sos_lp, signal.sosfilt(sos_lp, mono))
    
    if boost_bass:
        # Punchy 45-80Hz sub-bass boost (+7dB) with warm analog-style saturation
        sub_bass_mono = np.tanh(sub_bass_mono * 2.2) * 1.35
    
    sos_hp = signal.butter(2, preset.bass_crossover_hz, 'high', fs=sr, output='sos')
    spatial_band_l = signal.sosfilt(sos_hp, signal.sosfilt(sos_hp, left_orig))
    spatial_band_r = signal.sosfilt(sos_hp, signal.sosfilt(sos_hp, right_orig))
    spatial_band_mono = (spatial_band_l + spatial_band_r) * 0.5
    
    # 2. 2D Orbit Geometry
    omega = 2.0 * np.pi / preset.rotation_period
    azimuth = (omega * t) % (2.0 * np.pi)
    source_x = preset.orbit_radius * np.sin(azimuth)
    source_y = preset.orbit_radius * np.cos(azimuth)
    
    dist_l = np.sqrt((source_x + HEAD_RADIUS)**2 + source_y**2)
    dist_r = np.sqrt((source_x - HEAD_RADIUS)**2 + source_y**2)
    
    toa_l = dist_l / SPEED_OF_SOUND
    toa_r = dist_r / SPEED_OF_SOUND
    min_toa = np.minimum(toa_l, toa_r)
    
    itd_samples_l = (toa_l - min_toa) * sr
    itd_samples_r = (toa_r - min_toa) * sr
    
    gain_dist_l = preset.orbit_radius / dist_l
    gain_dist_r = preset.orbit_radius / dist_r
    
    pan_norm = np.sin(azimuth)
    pan_gain_l = np.cos((pan_norm + 1.0) * (np.pi / 4.0))
    pan_gain_r = np.sin((pan_norm + 1.0) * (np.pi / 4.0))
    
    pan_gain_l = (1.0 - preset.crossfeed_min) * pan_gain_l + preset.crossfeed_min * 0.707
    pan_gain_r = (1.0 - preset.crossfeed_min) * pan_gain_r + preset.crossfeed_min * 0.707
    
    # 3. Pinna & Rear Head Shadowing
    rear_factor = np.clip(-source_y / preset.orbit_radius, 0.0, 1.0)
    sos_hf = signal.butter(2, 4500.0, 'high', fs=sr, output='sos')
    spatial_hf_mono = signal.sosfilt(sos_hf, spatial_band_mono)
    spatial_mf_mono = spatial_band_mono - spatial_hf_mono
    
    rear_attenuation = 10.0 ** (-preset.pinna_rear_damping_db * rear_factor / 20.0)
    spatial_hf_damped = spatial_hf_mono * rear_attenuation
    spatial_cue_signal = spatial_mf_mono + spatial_hf_damped
    
    # 4. ITD Delay + ILD Application
    spatial_delayed_l = fractional_delay(spatial_cue_signal, itd_samples_l)
    out_spatial_l = spatial_delayed_l * gain_dist_l * pan_gain_l
    
    spatial_delayed_r = fractional_delay(spatial_cue_signal, itd_samples_r)
    out_spatial_r = spatial_delayed_r * gain_dist_r * pan_gain_r
    
    # 5. Diffuse Reverb Bus
    rev_l, rev_r = simple_schroeder_reverb(spatial_band_mono, sr, wet=preset.reverb_wet, decay=preset.reverb_decay)
    
    # 6. Recombination & Limiter
    final_l = sub_bass_mono + out_spatial_l + rev_l
    final_r = sub_bass_mono + out_spatial_r + rev_r
    
    peak = max(np.max(np.abs(final_l)), np.max(np.abs(final_r)))
    if peak > 0.95:
        final_l = np.tanh(final_l / peak) * 0.95
        final_r = np.tanh(final_r / peak) * 0.95
        
    out_stereo = np.vstack([final_l, final_r]).T
    wav.write(output_wav_path, sr, (out_stereo * 32767).astype(np.int16))
    return output_wav_path
