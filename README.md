GUI for ffmpeg for video trimming. It uses these flags:

.\ffmpeg.exe -i $input_path -ss $start -to $end -c:v libx264 -crf 18 -preset medium -c:a aac -b:a 128k $output_file