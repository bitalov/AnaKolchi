import streamlit as st
import re
import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from tafrigh import Config, TranscriptType, farrigh

# Load environment variables from .env file
load_dotenv()

# Define Wit.ai API keys for languages using environment variables
LANGUAGE_API_KEYS = {
    'EN': os.getenv('WIT_API_KEY_ENGLISH'),
    'AR': os.getenv('WIT_API_KEY_ARABIC'),
    'FR': os.getenv('WIT_API_KEY_FRENCH'),
    'JA': os.getenv('WIT_API_KEY_JAPANESE'),
    # Add more languages and API keys as needed
}

# Check if at least one API key is provided
if not any(LANGUAGE_API_KEYS.values()):
    st.error("Error: At least one Wit.ai API key must be provided in the .env file.")
    st.stop()

def download_youtube_video(youtube_url):
    st.text("Downloading YouTube video...")
    progress_bar = st.progress(0)
    
    output_path = Path('downloads') / '%(id)s.%(ext)s'
    command = ['yt-dlp', '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4', '-o', str(output_path), youtube_url]
    subprocess.run(command, check=True)
    video_file = next(Path('downloads').glob('*.mp4'))

    progress_bar.progress(25)
    return video_file

def extract_audio(file_path):
    st.text("Extracting audio from video...")
    progress_bar.progress(50)
    
    audio_output_path = file_path.with_suffix('.wav')
    command = ['ffmpeg', '-i', str(file_path), '-vn', '-acodec', 'pcm_s16le', '-ar', '22050', '-ac', '1', str(audio_output_path)]
    subprocess.run(command, check=True)

    progress_bar.progress(75)
    return audio_output_path

def clean_srt_file(srt_path):
    st.text("Cleaning SRT file...")
    progress_bar.progress(85)
    
    invisible_char_pattern = re.compile(r'[\u200B-\u200D\uFEFF]')
    square_pattern = re.compile(r'[\u25A0-\u25FF]')
    non_printable_pattern = re.compile(r'[\x00-\x1F\x7F-\x9F]')

    cleaned_srt_path = srt_path.with_name(srt_path.stem + '_cleaned.srt')

    with open(srt_path, 'r', encoding='utf-8') as infile, open(cleaned_srt_path, 'w', encoding='utf-8') as outfile:
        for line in infile:
            cleaned_line = invisible_char_pattern.sub('', line)
            cleaned_line = square_pattern.sub('', cleaned_line)
            cleaned_line = non_printable_pattern.sub('', cleaned_line)
            outfile.write(cleaned_line)
    
    progress_bar.progress(90)
    return cleaned_srt_path

def merge_subtitles(video_path, srt_path, language):
    st.text("Merging subtitles with video...")
    progress_bar.progress(95)
    
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
    
    subtitles_filter = f"subtitles='{srt_path_str}':charenc=UTF-8:force_style='FontName={font_name},FontSize={font_size}'"
    command = ['ffmpeg', '-hwaccel', 'auto', '-i', str(video_path), '-vf', subtitles_filter, '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'copy', str(output_path)]
    subprocess.run(command, check=True)

    progress_bar.progress(100)
    return output_path

def transcribe_file(file_path, language_sign):
    st.text("Transcribing audio file...")
    progress_bar.progress(30)
    
    if not is_wav_file(file_path):
        st.error(f"Skipping file {file_path} as it is not in WAV format.")
        return None

    wit_api_key = LANGUAGE_API_KEYS.get(language_sign.upper())
    if not wit_api_key:
        st.error(f"API key not found for language: {language_sign}")
        return None

    config = Config(
        urls_or_paths=[str(file_path)],
        skip_if_output_exist=False,
        playlist_items="",
        verbose=False,
        model_name_or_path="small",
        task="",
        language=language_sign.lower(),
        use_faster_whisper=True,
        beam_size=5,
        ct2_compute_type="",
        wit_client_access_tokens=[wit_api_key],
        max_cutting_duration=5,
        min_words_per_segment=1,
        save_files_before_compact=False,
        save_yt_dlp_responses=False,
        output_sample=0,
        output_formats=[TranscriptType.TXT, TranscriptType.SRT],
        output_dir=os.path.join(str(file_path.parent)),
    )

    farrigh_progress = list(farrigh(config))
    progress_bar.progress(80)

    srt_file = Path(os.path.join(str(file_path.parent), f"{file_path.stem}.srt"))
    txt_file = Path(os.path.join(str(file_path.parent), f"{file_path.stem}.txt"))

    if srt_file.exists() and srt_file.stat().st_size > 0 and txt_file.exists() and txt_file.stat().st_size > 0:
        st.success(f"Transcription completed. Check the output directory for the generated files.")
        cleaned_srt_file = clean_srt_file(srt_file)
        return cleaned_srt_file
    else:
        st.error("Transcription failed. No SRT or TXT file was generated, or the file sizes are 0.")

    return None

def main():
    st.title("AnaKolchi - Sous Titre Kolchiii")
    source_type = st.radio("Choose the source type:", ("YouTube video", "Local file"))
    language_sign = st.selectbox("Select the language:", list(LANGUAGE_API_KEYS.keys()))

    if source_type == "YouTube video":
        youtube_url = st.text_input("Enter the YouTube video link:")
        if st.button("Transcribe YouTube video"):
            if youtube_url and language_sign:
                video_file = download_youtube_video(youtube_url)
                audio_file = extract_audio(video_file)
                srt_path = transcribe_file(audio_file, language_sign)
                if srt_path:
                    merged_video = merge_subtitles(video_file, srt_path, language_sign)
                    st.video(str(merged_video))
                    with open(merged_video, "rb") as file:
                        st.download_button("Download Video with Subtitles", file, file_name=merged_video.name)
            else:
                st.error("Please provide both the YouTube video link and the language.")
    else:
        file_path = st.file_uploader("Upload a local file:", type=['wav', 'mp3', 'mp4', 'mkv', 'avi'])
        if st.button("Transcribe Local File") and file_path and language_sign:
            with open(file_path.name, "wb") as f:
                f.write(file_path.getvalue())
            file_path = Path(file_path.name)
            if file_path.suffix.lower() in ['.mp4', '.mkv', '.avi']:
                audio_file = extract_audio(file_path)
            else:
                audio_file = file_path
            srt_path = transcribe_file(audio_file, language_sign)
            if srt_path:
                if file_path.suffix.lower() in ['.mp4', '.mkv', '.avi']:
                    merged_video = merge_subtitles(file_path, srt_path, language_sign)
                    st.video(str(merged_video))
                    with open(merged_video, "rb") as file:
                        st.download_button("Download Video with Subtitles", file, file_name=merged_video.name)
                else:
                    st.download_button("Download SRT", data=open(srt_path, "rb"), file_name="transcription.srt")

if __name__ == "__main__":
    main()
