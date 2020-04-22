import subprocess
from audiotsm import phasevocoder
from audiotsm.io.wav import WavReader, WavWriter
from scipy.io import wavfile
import numpy as np
import re
import math
from shutil import copyfile, rmtree, move
import os, sys
import argparse
from datetime import datetime
import random

import ytdl

def getMaxVolume(s):
    maxv = float(np.max(s))
    minv = float(np.min(s))
    return max(maxv,-minv)

def copyFrame(inputFrame, outputFrame):
    src = f"{TEMP_FOLDER}/frame{(inputFrame+1):06}.jpg"
    dst = f"{TEMP_FOLDER}/newFrame{(outputFrame+1):06}.jpg"

    if frameMap[inputFrame] == -1:
        if not os.path.isfile(src):
            return False
        move(src, dst)
        frameMap[inputFrame] = outputFrame
    else:
        src = f"{TEMP_FOLDER}/newFrame{(frameMap[inputFrame]+1):06}.jpg"
        if not os.path.isfile(src):
            return False
        copyfile(src, dst)

    if outputFrame%500 == 499 and not args.silent:
        print(f"{outputFrame+1} time-altered frames saved.")
    return True

def appendToFileName(filename, extra):
    dotIndex = filename.rfind(".")
    return filename[:dotIndex]+extra+filename[dotIndex:]


def error(msg, fatal=True):
    print("[ERROR]", msg)
    if fatal:
        sys.exit(1)

def log(msg, box=False):
    if args.silent:
        print(msg)
    else:
        bar = "#" * 120
        print(bar)
        print("#", msg)
        print(bar)


start_time = datetime.now()

parser = argparse.ArgumentParser(description='Modifies a video file to play at different speeds when there is sound vs. silence.')
parser.add_argument('input_file', type=str,  help='the video file you want modified or a youtube url')
parser.add_argument('-o', '--output_file', type=str, default="", help="the output file. (optional. if not included, it'll just modify the input file name)")
parser.add_argument('--silent_threshold', type=float, default=0.03, help="the volume amount that frames' audio needs to surpass to be consider \"sounded\". It ranges from 0 (silence) to 1 (max volume)")
parser.add_argument('--sounded_speed', type=float, default=1.00, help="the speed that sounded (spoken) frames should be played at. Typically 1.")
parser.add_argument('--silent_speed', type=float, default=10.00, help="the speed that silent frames should be played at. 999999 for jumpcutting.")
parser.add_argument('--frame_margin', type=float, default=3, help="some silent frames adjacent to sounded frames are included to provide context. How many frames on either the side of speech should be included? That's this variable.")
parser.add_argument('--sample_rate', type=float, default=44100, help="sample rate of the input and output videos")
parser.add_argument('--frame_rate', type=float, default=30, help="frame rate of the input and output videos. optional... I try to find it out myself, but it doesn't always work.")
parser.add_argument('--frame_quality', type=int, default=2, help="quality of frames to be extracted from input video. 1 is highest, 31 is lowest, 3 is the default.")
parser.add_argument('-s', '--silent', action='store_true', help="hide most output messages")
parser.add_argument('--ffmpeg_path', type=str, default="ffmpeg", help="the path to the ffmpeg binary")

args = parser.parse_args()


FRAME_RATE = args.frame_rate
SAMPLE_RATE = args.sample_rate
SILENT_THRESHOLD = args.silent_threshold
FRAME_SPREADAGE = args.frame_margin
NEW_SPEED = [args.silent_speed, args.sounded_speed]

INPUT_FILE = args.input_file
FRAME_QUALITY = args.frame_quality
SILENT = args.silent
FFMPEG_PATH = args.ffmpeg_path

TEMP_FOLDER = f"TEMP_{random.randint(10**8, 10**9 - 1)}"
AUDIO_FADE_ENVELOPE_SIZE = 400 # smooth out transitiion's audio by quickly fading in/out (arbitrary magic number whatever)


# check if we need to download the video first
if ytdl.is_youtube_url(INPUT_FILE):
    log(f"Downloading {INPUT_FILE}")
    cb = None if args.silent else lambda x: print(f"Downloaded {x}%")
    try:
        INPUT_FILE = ytdl.download_video(INPUT_FILE, progress_callback=cb)
    except:
        error(f"Failed to download `{INPUT_FILE}`.")

# check input file
if not os.path.isfile(INPUT_FILE):
    error(f"Input file `{INPUT_FILE}` not found.")

# create TMP directory
try:
    os.mkdir(TEMP_FOLDER)
except OSError:
    if not os.path.isdir(TEMP_FOLDER):
        error(f"Failed to create temporary directory (`{TEMP_FOLDER}`)")

# detect framerate
p = subprocess.run([FFMPEG_PATH, "-hide_banner" ,"-i", INPUT_FILE], capture_output=True, encoding="ascii")
for line in p.stderr.split("\n"):
    match = re.search('Stream #.*Video.* ([0-9\\.]*) fps', line)
    if match:
        FRAME_RATE = float(match.group(1))
        break

# extract frames
log("Extracting frames...")
p = subprocess.run([FFMPEG_PATH, "-hide_banner", "-i", INPUT_FILE, "-qscale:v", str(FRAME_QUALITY), TEMP_FOLDER + "/frame%06d.jpg"])
if p.returncode:
    error(f"ffmpeg terminated with code {p.returncode}.")

# extract audio
log("Extracting audio...")
p = subprocess.run([FFMPEG_PATH, "-hide_banner", "-i", INPUT_FILE, "-ab", "160k", "-ac", "2", "-ar", str(SAMPLE_RATE), "-vn", "-y", TEMP_FOLDER + "/audio.wav"])
if p.returncode:
    error(f"ffmpeg terminated with code {p.returncode}.")

# TODO refactor

sampleRate, audioData = wavfile.read(TEMP_FOLDER + "/audio.wav")
audioSampleCount = audioData.shape[0]
maxAudioVolume = getMaxVolume(audioData)


samplesPerFrame = sampleRate/FRAME_RATE

audioFrameCount = int(math.ceil(audioSampleCount/samplesPerFrame))

hasLoudAudio = np.zeros((audioFrameCount))



for i in range(audioFrameCount):
    start = int(i*samplesPerFrame)
    end = min(int((i+1)*samplesPerFrame),audioSampleCount)
    audiochunks = audioData[start:end]
    maxchunksVolume = float(getMaxVolume(audiochunks))/maxAudioVolume
    if maxchunksVolume >= SILENT_THRESHOLD:
        hasLoudAudio[i] = 1

chunks = [[0,0,0]]
shouldIncludeFrame = np.zeros((audioFrameCount))
for i in range(audioFrameCount):
    start = int(max(0,i-FRAME_SPREADAGE))
    end = int(min(audioFrameCount,i+1+FRAME_SPREADAGE))
    shouldIncludeFrame[i] = np.max(hasLoudAudio[start:end])
    if (i >= 1 and shouldIncludeFrame[i] != shouldIncludeFrame[i-1]): # Did we flip?
        chunks.append([chunks[-1][1],i,shouldIncludeFrame[i-1]])

chunks.append([chunks[-1][1],audioFrameCount,shouldIncludeFrame[i-1]])
chunks = chunks[1:]

outputAudioData = np.zeros((0,audioData.shape[1]))
outputPointer = 0

log("Selecting frames...")

frameMap = np.full(audioFrameCount, -1) # an array to map where to find the old frames

frames = 0

lastExistingFrame = None
for chunk in chunks:
    audioChunk = audioData[int(chunk[0]*samplesPerFrame):int(chunk[1]*samplesPerFrame)]

    sFile = TEMP_FOLDER+"/tempStart.wav"
    eFile = TEMP_FOLDER+"/tempEnd.wav"
    wavfile.write(sFile,SAMPLE_RATE,audioChunk)
    with WavReader(sFile) as reader:
        with WavWriter(eFile, reader.channels, reader.samplerate) as writer:
            tsm = phasevocoder(reader.channels, speed=NEW_SPEED[int(chunk[2])])
            tsm.run(reader, writer)
    _, alteredAudioData = wavfile.read(eFile)
    leng = alteredAudioData.shape[0]
    endPointer = outputPointer+leng
    outputAudioData = np.concatenate((outputAudioData,alteredAudioData/maxAudioVolume))

    # smooth out transitiion's audio by quickly fading in/out

    if leng < AUDIO_FADE_ENVELOPE_SIZE:
        outputAudioData[outputPointer:endPointer] = 0 # audio is less than 0.01 sec, let's just remove it.
    else:
        premask = np.arange(AUDIO_FADE_ENVELOPE_SIZE)/AUDIO_FADE_ENVELOPE_SIZE
        mask = np.repeat(premask[:, np.newaxis],2,axis=1) # make the fade-envelope mask stereo
        outputAudioData[outputPointer:outputPointer+AUDIO_FADE_ENVELOPE_SIZE] *= mask
        outputAudioData[endPointer-AUDIO_FADE_ENVELOPE_SIZE:endPointer] *= 1-mask

    startOutputFrame = int(math.ceil(outputPointer/samplesPerFrame))
    endOutputFrame = int(math.ceil(endPointer/samplesPerFrame))
    for outputFrame in range(startOutputFrame, endOutputFrame):
        frames += 1
        inputFrame = int(chunk[0]+NEW_SPEED[int(chunk[2])]*(outputFrame-startOutputFrame))
        didItWork = copyFrame(inputFrame,outputFrame)
        if didItWork:
            lastExistingFrame = inputFrame
        else:
            copyFrame(lastExistingFrame,outputFrame)

    outputPointer = endPointer

wavfile.write(TEMP_FOLDER+"/audioNew.wav",SAMPLE_RATE,outputAudioData)

# ratio of frame reduction
ratio = int((audioFrameCount / frames) * 100 - 100)

if len(args.output_file) >= 1:
    OUTPUT_FILE = args.output_file
else:
    OUTPUT_FILE = appendToFileName(INPUT_FILE, f" - jumpcut {ratio}% faster")

# render new video
log("Rendering video...")
p = subprocess.run([FFMPEG_PATH,  "-hide_banner", "-framerate", str(FRAME_RATE), "-i", TEMP_FOLDER + "/newFrame%06d.jpg", "-i", TEMP_FOLDER + "/audioNew.wav", "-strict", "-2", "-y", OUTPUT_FILE])
if p.returncode:
    error(f"ffmpeg terminated with code {p.returncode}.")

log(f"Done. Speedup: {ratio}% ({audioFrameCount} -> {frames}). Saved to {OUTPUT_FILE}. Time: {datetime.now() - start_time}")

# cleanup, delete temp dir
try:
    rmtree(TEMP_FOLDER, ignore_errors=False)
except OSError:
    error(f"Failed to delete directory {TEMP_FOLDER}", fatal=False)
