#!/bin/bash
cd /c/01_CODING/18_CODINGHARD_6/Pixels2MetroPolicy/video_thailand_disasters
FF=./bin/ffmpeg.exe
FONT=arialbd.ttf
VF="scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1,fade=t=in:st=0:d=0.25,fade=t=out:st=4.7:d=0.3"
AF="afade=t=in:st=0:d=0.2,afade=t=out:st=4.7:d=0.3"
OUT=thailand_review_60s.mp4

rm -f clips/[0-9][0-9]_*.mp4

$FF -y -nostdin -v error -f lavfi -i color=black:s=1280x720:d=3:r=30 -f lavfi -i anullsrc=r=44100:cl=stereo \
 -vf "drawtext=fontfile=$FONT:text='THAILAND REVIEW':fontsize=64:fontcolor=white:x=(w-text_w)/2:y=300,drawtext=fontfile=$FONT:text='flood . fire . blast . storm . tsunami':fontsize=28:fontcolor=0xCCCCCC:x=(w-text_w)/2:y=390" \
 -t 3 -c:v libx264 -crf 21 -preset fast -pix_fmt yuv420p -c:a aac -b:a 128k -ar 44100 -ac 2 clips/00_title.mp4 && echo "ok title"

$FF -y -nostdin -v error -f lavfi -i color=black:s=1280x720:d=2:r=30 -f lavfi -i anullsrc=r=44100:cl=stereo \
 -vf "drawtext=fontfile=$FONT:text='Sources - YouTube news footage':fontsize=26:fontcolor=0x999999:x=(w-text_w)/2:y=(h-text_h)/2" \
 -t 2 -c:v libx264 -crf 21 -preset fast -pix_fmt yuv420p -c:a aac -b:a 128k -ar 44100 -ac 2 clips/99_end.mp4 && echo "ok end"

CLIPS=(
 "26Cce14I6Lo|290|BANGKOK - MONSOON FLOOD"
 "Vm8tGfI9J5s|38|BANGKOK - KHLONG TOEI SLUM FIRE"
 "hmVAq9MZ52o|88|SAMUT PRAKAN - FACTORY BLAST"
 "_nivmGHV-VQ|150|BANGKOK - KHLONG TOEI, 20 HOMES BURNED"
 "ZGit8udvdfQ|108|BANGKOK - CANAL DISTRICTS FLOODED"
 "P3hYez490Ug|56|BANGKOK - CANALSIDE COMMUNITY FLOOD"
 "lfo-81nB2DM|52|CHAO PHRAYA - BARRIER COLLAPSE"
 "axokUjC16kc|97|CHIANG MAI - WILDFIRES"
 "5DjO6OXkW6k|186|PATTAYA - NIGHT FLOOD"
 "0sxHHPnSIsI|155|PHUKET - FLASH FLOOD"
 "tl_y_OAMn9E|5|PHUKET - PATONG SLUM FIRE"
 "_AZ6TuEubQA|55|PHUKET - 2004 TSUNAMI"
 "EXxQ2puTvOg|40|HAT YAI - CITY SUBMERGED"
 "Sl5QAR7MZaE|3|HAT YAI - ROOFTOP RESCUE"
 "vFgFdMxSL7Y|25|TROPICAL STORM PABUK"
)
n=0
for c in "${CLIPS[@]}"; do
  n=$((n+1))
  id=${c%%|*}; rest=${c#*|}; start=${rest%%|*}; label=${rest#*|}
  fn=$(printf 'clips/%02d_%s.mp4' "$n" "$id")
  $FF -y -nostdin -v error -ss "$start" -t 5 -i "dl/$id.mp4" \
   -vf "$VF,drawtext=fontfile=$FONT:text='$label':fontsize=34:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=12:x=24:y=h-text_h-24" \
   -af "$AF" -c:v libx264 -crf 21 -preset fast -pix_fmt yuv420p -c:a aac -b:a 160k -ar 44100 -ac 2 "$fn" \
   && echo "ok $fn" || echo "FAIL $fn"
done

: > list.txt
echo "file 'clips/00_title.mp4'" >> list.txt
for f in $(ls clips/[0-9][0-9]_*.mp4 | grep -v 00_title | grep -v 99_end | sort); do echo "file '$f'" >> list.txt; done
echo "file 'clips/99_end.mp4'" >> list.txt
$FF -y -nostdin -v error -f concat -safe 0 -i list.txt -c copy -movflags +faststart "$OUT" && echo "ok final"
./bin/ffprobe.exe -v error -show_entries format=duration -of csv=p=0 "$OUT"
