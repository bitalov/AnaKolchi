import streamlit as st
import sys
import re
import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from tafrigh import Config, TranscriptType, farrigh
import anthropic

# Load environment variables from .env file
load_dotenv()

# Define Wit.ai API keys for languages using environment variables
LANGUAGE_API_KEYS = {
    'AR': os.getenv('WIT_API_KEY_ARABIC'),
    'EN': os.getenv('WIT_API_KEY_ENGLISH'),
    'FR': os.getenv('WIT_API_KEY_FRENCH'),
    'JA': os.getenv('WIT_API_KEY_JAPANESE'),
    # Add more languages and API keys as needed
}

# Check if at least one API key is provided
if not any(LANGUAGE_API_KEYS.values()):
    st.error("Error: At least one Wit.ai API key must be provided in the .env file.")
    st.stop()

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

if not ANTHROPIC_API_KEY:
    st.error("Error: Anthropic API key must be provided in the .env file.")
    st.stop()


anthropic_client = anthropic.Anthropic(
    api_key=ANTHROPIC_API_KEY,
)

def download_youtube_video(youtube_url, progress_bar):
    st.text("Downloading YouTube video...")
    progress_bar.progress(25)
    
    output_path = Path('downloads') / '%(id)s.%(ext)s'
    command = ['yt-dlp', '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4', '-o', str(output_path), youtube_url]
    subprocess.run(command, check=True)
    video_file = next(Path('downloads').glob('*.mp4'))

    progress_bar.progress(30)
    return video_file

def extract_audio(file_path, progress_bar):
    st.text("Extracting audio from video...")
    progress_bar.progress(30)
    
    audio_output_path = file_path.with_suffix('.wav')
    command = ['ffmpeg', '-i', str(file_path), '-vn', '-acodec', 'pcm_s16le', '-ar', '22050', '-ac', '1', str(audio_output_path)]
    subprocess.run(command, check=True)

    progress_bar.progress(50)
    return audio_output_path

def clean_srt_file(srt_path, progress_bar):
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

def merge_subtitles(video_path, srt_path, language, progress_bar):
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

def is_wav_file(file_path):
    try:
        with open(file_path, 'rb') as file:
            return file.read(4) == b'RIFF'
    except IOError:
        return False
    
def transcribe_file(file_path, language_sign, progress_bar):
    st.text("Transcribing audio file...")
    progress_bar.progress(50)
    
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
    progress_bar.progress(90)

    srt_file = Path(os.path.join(str(file_path.parent), f"{file_path.stem}.srt"))
    txt_file = Path(os.path.join(str(file_path.parent), f"{file_path.stem}.txt"))

    if srt_file.exists() and srt_file.stat().st_size > 0 and txt_file.exists() and txt_file.stat().st_size > 0:
        st.success(f"Transcription completed. Check the output directory for the generated files.")
        #cleaned_srt_file = clean_srt_file(srt_file, progress_bar)
        return srt_file
    else:
        st.error("Transcription failed. No SRT or TXT file was generated, or the file sizes are 0.")

    return None
def count_srt_words(srt_path):
    with open(srt_path, 'r', encoding='utf-8') as infile:
        content = infile.read()
        return len(content.split())

def translate_subtitles(srt_path, target_language, progress_bar):
    st.text("Translating subtitles...")
    progress_bar.progress(85)
    translated_srt_path = srt_path.with_name(srt_path.stem + f'_translated_{target_language}.srt')
    prompt = f"Translate the following SRT file to the target following language {target_language}"
    with open(srt_path, 'r', encoding='utf-8') as infile:
        for line in infile:
            prompt += line
    srt_word_count = count_srt_words(srt_path)
    # Ratio between tokens and English words is 0.75 I think the it changes from language to language so
    # Assumptions below to support other languages hopefully without issues
    max_tokens_estimated = (srt_word_count * 2) * 4 + 500  # Assuming an average of 4 tokens per word, plus an offset of 500 tokens
    message = anthropic_client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=max_tokens_estimated,
        temperature=0.2,
        system="Detect what's language / Dialect automaticaly and Respect and preserve SRT file format",
        messages=[
        {"role": "user", "content": prompt} 
    ]
    )
    translated_srt = message.content[0].text
    translated_srt_lines = (translated_srt.split('\n'))[2:]
    translated_srt = '\n'.join(translated_srt_lines)
    with open(translated_srt_path, 'w', encoding='utf-8') as outfile:
        outfile.write(translated_srt)
    progress_bar.progress(90)
    return translated_srt_path

def translate_subtitles_debug(srt_path, target_language):
    st.text("Translating subtitles...")
    #progress_bar.progress(85)

    translated_srt_path = srt_path.with_name(srt_path.stem + f'_translated_{target_language}.srt')

    with open(srt_path, 'r', encoding='utf-8') as infile:
        prompt = "Detect what's language / Dialect and Translate the following SRT file to the target language while preserving the SRT format:\n\n"
        for line in infile:
            prompt += line

        srt_word_count = count_srt_words(srt_path)
        # Ratio between tokens and English words is 0.75 I think the it changes from language to language so
        # Assumptions below to support other languages hopefully without issues
        max_tokens_to_sample = (srt_word_count * 2) * 4 + 500  # Assuming an average of 4 tokens per word, plus an offset of 500 tokens

        response = anthropic_client.completions.create(
            prompt=prompt,
            model="claude-3-haiku-20240307",
            max_tokens_to_sample=max_tokens_to_sample,
            temperature=0.2,
        )
        translated_srt = response.completion

        with open(translated_srt_path, 'w', encoding='utf-8') as outfile:
            outfile.write(translated_srt)

    
    #progress_bar.progress(90)
    return translated_srt_path

def main():

    st.title("AnaKolchi - Sous Titre Kolchiii")
    source_type = st.radio("Choose the source type:", ("YouTube video", "Local file"))
    language_sign = st.selectbox("Select the language:", list(LANGUAGE_API_KEYS.keys()))
    target_language = st.selectbox("Select the target language for translation:", ['en', 'ar', 'fr', 'ja', 'es', 'de'])

    if source_type == "YouTube video":
        youtube_url = st.text_input("Enter the YouTube video link:")
        transcribe_button = st.button("Transcribe YouTube video")
    else:
        file_path = st.file_uploader("Upload a local file:", type=['wav', 'mp3', 'mp4', 'mkv', 'avi'])
        transcribe_button = st.button("Transcribe Local File")

    if transcribe_button:
        progress_bar = st.progress(0)
        if source_type == "YouTube video" and youtube_url and language_sign:
            video_file = download_youtube_video(youtube_url, progress_bar)
            audio_file = extract_audio(video_file, progress_bar)
            srt_path = transcribe_file(audio_file, language_sign, progress_bar)
        elif source_type == "Local file" and file_path and language_sign:
            with open(file_path.name, "wb") as f:
                f.write(file_path.getvalue())
            file_path = Path(file_path.name)
            if file_path.suffix.lower() in ['.mp4', '.mkv', '.avi']:
                audio_file = extract_audio(file_path, progress_bar)
            else:
                audio_file = file_path
            srt_path = transcribe_file(audio_file, language_sign, progress_bar)
        else:
            st.error("Please provide the required inputs.")
            return

        if srt_path:
            # Download original SRT and TXT
            with open(srt_path, "rb") as file:
                st.download_button("Download Original SRT", file, file_name=srt_path.name)
            txt_path = srt_path.with_suffix('.txt')
            with open(txt_path, "rb") as file:
                st.download_button("Download Original TXT Transcription", file, file_name=txt_path.name)

            # Translate subtitles
            translated_srt_path = translate_subtitles(srt_path, target_language, progress_bar)
            if translated_srt_path:
                # Download translated SRT
                with open(translated_srt_path, "rb") as file:
                    st.download_button(f"Download Translated SRT ({target_language.upper()})", file, file_name=translated_srt_path.name)
                
                # Merge subtitles with video
                merged_video = merge_subtitles(video_file, translated_srt_path, target_language, progress_bar)
                st.video(str(merged_video))
                with open(merged_video, "rb") as file:
                    st.download_button("Download Video with Translated Subtitles", file, file_name=merged_video.name)
            else:
                st.error("Translation failed.")
        else:
            st.error("Transcription failed.")

if __name__ == "__main__":
    main()
