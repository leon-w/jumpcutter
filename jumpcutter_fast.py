import subprocess
import random
import sys
import os
from datetime import datetime
import argparse
import atexit
import numpy as np
from scipy.io import wavfile
import librosa

# input params
parser = argparse.ArgumentParser(description="Removes silence from a video")
parser.add_argument("input_file", type=str, help="the video file you want modified")
parser.add_argument("-db", type=float, default=40, help="db threshold of the parts to remove")
parser.add_argument("-out_format", type=str, default="mp4", help="format of output file")
parser.add_argument("-w", action="store_true", help="directly watch video with vlc")
parser.add_argument("-vlc_path", type=str, default="/Applications/VLC.app/Contents/MacOS/VLC", help="path to vlc")

args = parser.parse_args()

salt = f"{random.randint(0, 10**5):05d}"
audio_file = f"JC_AUDIO_{salt}.wav"
script_file = f"JC_SCRIPT_{salt}.txt"

if args.w:
    args.out_format = "ts"


def run_ffmpeg(cmd):
    p = subprocess.run(["ffmpeg", *cmd])
    if p.returncode:
        print(f"ffmpeg terminated with code {p.returncode}.", file=sys.stderr)
        sys.exit(1)


def cleanup():
    try:
        os.remove(audio_file)
        os.remove(script_file)
    except:
        pass


atexit.register(cleanup)

start_time = datetime.now()

# extract audio
run_ffmpeg(["-i", args.input_file, "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000", audio_file])
sample_rate, audio_data = wavfile.read(audio_file)

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
out_file = args.input_file.rsplit(".", 1)[0] + f" ({frac}%).{args.out_format}"

if args.w:
    subprocess.Popen([args.vlc_path, out_file, "--quiet"])

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
        "-c:v",
        "libx264",
        out_file,
        "-y",
    ]
)

print(f"Done. Saved to {out_file}. Time: {datetime.now() - start_time}")
