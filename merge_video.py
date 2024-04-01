import streamlit as st
import sys
import re
import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from tafrigh import Config, TranscriptType, farrigh
import anthropic


def merge_subtitles(video_path, srt_path, language, progress_bar=None):
    #st.text("Merging subtitles with video...")
    #progress_bar.progress(95)
    
    output_path = video_path.with_name(video_path.stem + '_with_subs.mp4')
    srt_path_str = str(srt_path.resolve()).replace('\\', '\\\\').replace(':', '\\:')

    font_size = 24
    font_name = 'Arial'

    language_fonts = {
        'EN': ('Arial', 24),
        'AR': ('Times New Roman', 28),
        'JA': ('MS PGothic', 28),
        # Add more language-font mappings as needed
    }

    if language in language_fonts:
        font_name, font_size = language_fonts[language]
    
    subtitles_filter = f"subtitles='{srt_path_str}':force_style='FontName={font_name},FontSize={font_size}'"
    command = ['ffmpeg', '-hwaccel', 'auto', '-i', str(video_path), '-vf', subtitles_filter, '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'copy', str(output_path)]
    subprocess.run(command, check=True)

    #progress_bar.progress(100)
    return output_path


video_path = Path(r"C:\Users\bilal\OneDrive\Desktop\AnaKolchi\downloads\mNDj_YT971A.mp4")
srt_path = Path(r"C:\Users\bilal\OneDrive\Desktop\AnaKolchi\downloads\mNDj_YT971A_translated_en.srt")
language = "EN"  # Specify the language code
output_path = merge_subtitles(video_path, srt_path, language)

# Print the output path
    #print("Merged video with subtitles saved at:", output_path)
    #sys.exit(0)