# jumpcutter

Shorten videos by removing silence. Explanation here: https://www.youtube.com/watch?v=DQ8orIurGxw
Tested on Windows 10 (should work on other systems).

## Prerequisites

* `Python3`
* `ffmpeg`

## Usage
```
usage: jumpcutter.py [-h] [-o OUTPUT_FILE] [--silent_threshold SILENT_THRESHOLD] [--sounded_speed SOUNDED_SPEED]
                     [--silent_speed SILENT_SPEED] [--frame_margin FRAME_MARGIN] [--sample_rate SAMPLE_RATE]
                     [--frame_rate FRAME_RATE] [--frame_quality FRAME_QUALITY] [-s] [--ffmpeg_path FFMPEG_PATH]
                     input_file

Modifies a video file to play at different speeds when there is sound vs. silence.

positional arguments:
  input_file            the video file you want modified

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUT_FILE, --output_file OUTPUT_FILE
                        the output file. (optional. if not included, it'll just modify the input file name)
  --silent_threshold SILENT_THRESHOLD
                        the volume amount that frames' audio needs to surpass to be consider "sounded". It ranges
                        from 0 (silence) to 1 (max volume)
  --sounded_speed SOUNDED_SPEED
                        the speed that sounded (spoken) frames should be played at. Typically 1.
  --silent_speed SILENT_SPEED
                        the speed that silent frames should be played at. 999999 for jumpcutting.
  --frame_margin FRAME_MARGIN
                        some silent frames adjacent to sounded frames are included to provide context. How many
                        frames on either the side of speech should be included? That's this variable.
  --sample_rate SAMPLE_RATE
                        sample rate of the input and output videos
  --frame_rate FRAME_RATE
                        frame rate of the input and output videos. optional... I try to find it out myself, but
                        it doesn't always work.
  --frame_quality FRAME_QUALITY
                        quality of frames to be extracted from input video. 1 is highest, 31 is lowest, 3 is the
                        default.
  -s, --silent          hide most output messages
  --ffmpeg_path FFMPEG_PATH
                        the path to the ffmpeg binary

```

__Warning:__ The input video will get split into single frames so long videos will take up a lot of temporary disk space.
