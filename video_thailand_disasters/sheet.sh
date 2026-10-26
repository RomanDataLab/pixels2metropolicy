#!/bin/bash
cd /c/01_CODING/18_CODINGHARD_6/Pixels2MetroPolicy/video_thailand_disasters
id="$1"
dur=$(./bin/ffprobe.exe -v error -show_entries format=duration -of csv=p=0 "dl/$id.mp4")
step=$(echo "$dur 47" | awk '{s=int($1/$2)+1; if(s<2)s=2; print s}')
./bin/ffmpeg.exe -y -v error -i "dl/$id.mp4" -vf "fps=1/$step,scale=320:-1,tile=8x6" -frames:v 1 "sheets/$id.png"
echo "$id dur=$dur step=$step"
