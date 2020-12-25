import subprocess
import random
import sys
import os
from datetime import datetime
import argparse
import numpy as np
from scipy.io import wavfile
import librosa

# input params
parser = argparse.ArgumentParser(description="Removes silence from a video")
parser.add_argument("input_file", type=str, help="the video file you want modified")
parser.add_argument("-db", type=float, default=40, help="db threshold of the parts to remove")

args = parser.parse_args()

salt = f"{random.randint(0, 10**5):05d}"
audio_file = f"JC_AUDIO_{salt}.wav"
script_file = f"JC_SCRIPT_{salt}.txt"


def run_ffmpeg(cmd):
    p = subprocess.run(["ffmpeg", *cmd])
    if p.returncode:
        print(f"ffmpeg terminated with code {p.returncode}.", file=sys.stderr)
        sys.exit(1)


def appendToFileName(filename, extra):
    dotIndex = filename.rfind(".")
    return filename[:dotIndex] + extra + filename[dotIndex:]


start_time = datetime.now()

# extract audio
run_ffmpeg(["-i", args.input_file, "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000", audio_file])
sample_rate, audio_data = wavfile.read(audio_file)
os.remove(audio_file)

# select sounded parts
sounded_parts = librosa.effects.split(
    audio_data.astype(np.float32),
    top_db=args.db,
    frame_length=2048,
    hop_length=512,
)

# generate script
with open(script_file, "w") as f:
    for i, (a, b) in enumerate(sounded_parts):
        start = round(a / sample_rate, 3)
        end = round(b / sample_rate, 3)
        f.write(f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}];\n")
        f.write(f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}];\n")

    n = len(sounded_parts)
    streams_v = "".join(map(lambda x: f"[v{x}]", range(n)))
    streams_a = "".join(map(lambda x: f"[a{x}]", range(n)))
    f.write(f"{streams_v}concat=n={n}[vout];\n")
    f.write(f"{streams_a}concat=n={n}:v=0:a=1[aout]")

# render video
frac = int((sounded_parts[:, 1] - sounded_parts[:, 0]).sum() / len(audio_data) * 100)
out_file = appendToFileName(args.input_file, f" ({frac}%)")
run_ffmpeg(
    [
        "-i",
        args.input_file,
        "-filter_complex_script",
        script_file,
        "-map",
        "[vout]",
        "-map",
        "[aout]",
        out_file,
    ]
)
os.remove(script_file)

print(f"Done. Saved to {out_file}. Time: {datetime.now() - start_time}")
