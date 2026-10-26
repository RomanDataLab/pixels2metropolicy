#!/bin/bash
cd /c/01_CODING/18_CODINGHARD_6/Pixels2MetroPolicy/video_thailand_disasters
./bin/yt-dlp.exe -q --no-warnings -f "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]" --merge-output-format mp4 -o "dl/%(id)s.%(ext)s" "https://www.youtube.com/watch?v=$1" 2>>dlerr.log
echo "done $1"
