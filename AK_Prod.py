import tempfile
import base64
import sys
import re
import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from tafrigh import Config, TranscriptType, farrigh
import anthropic
import gradio as gr
import asyncio
import uuid


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
    print("Error: At least one Wit.ai API key must be provided in the .env file.")
    sys.exit()

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

if not ANTHROPIC_API_KEY:
    print("Error: Anthropic API key must be provided in the .env file.")
    sys.exit()

anthropic_client = anthropic.Anthropic(
    api_key=ANTHROPIC_API_KEY,
)

# Create queues for each function
#download_queue = queue()
#extract_queue = queue()
#transcribe_queue = queue()
#translate_queue = queue()
#merge_queue = queue()

#@download_queue.task
def download_youtube_video(youtube_url, progress=gr.Progress()):
    progress(0, "Downloading YouTube video...")
    unique_id = uuid.uuid4()  # Generate a random UUID
    output_path = Path('downloads') / f'{unique_id}.%(ext)s'  # Use the UUID as part of the file name
    command = ['yt-dlp', '-f', 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/mp4', '-o', str(output_path), youtube_url]
    subprocess.run(command, check=True)
    video_file = next(Path('downloads').glob(f'{unique_id}.mp4'))

    progress(0.1)
    return video_file

#@extract_queue.task
def extract_audio(file_path, progress=gr.Progress()):
    progress(0.1, "Extracting audio from video...")
    audio_output_path = file_path.with_suffix('.wav')
    command = ['ffmpeg', '-i', str(file_path), '-vn', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2', str(audio_output_path)]
    subprocess.run(command, check=True)

    progress(0.2)
    return audio_output_path

#@merge_queue.task
def merge_subtitles(video_path, srt_path, language, progress=gr.Progress()):
    progress(0.9, "Merging subtitles with video...")
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
    
    progress(1.0)
    return output_path

def is_wav_file(file_path):
    try:
        with open(file_path, 'rb') as file:
            return file.read(4) == b'RIFF'
    except IOError:
        return False

#@transcribe_queue.task
def transcribe_file(file_path, language_sign,progress=gr.Progress()):
    progress(0.2, "Transcribing audio file...")
    if not is_wav_file(file_path):
        print(f"Skipping file {file_path} as it is not in WAV format.")
        return None

    wit_api_key = LANGUAGE_API_KEYS.get(language_sign.upper())
    if not wit_api_key:
        print(f"API key not found for language: {language_sign}")
        return None

    config = Config(
        urls_or_paths=[str(file_path)],
        skip_if_output_exist=False,
        playlist_items="",
        verbose=False,
        model_name_or_path="medium",
        task="",
        language="",
        use_faster_whisper=False,
        beam_size=7,
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
    progress(0.7)

    srt_file = Path(os.path.join(str(file_path.parent), f"{file_path.stem}.srt"))
    txt_file = Path(os.path.join(str(file_path.parent), f"{file_path.stem}.txt"))

    if srt_file.exists() and srt_file.stat().st_size > 0 and txt_file.exists() and txt_file.stat().st_size > 0:
        return srt_file
    else:
        print("Transcription failed. No SRT or TXT file was generated, or the files are corrupted.")

    return None

def count_srt_words(srt_path):
    with open(srt_path, 'r', encoding='utf-8') as infile:
        content = infile.read()
        return len(content.split())

#@translate_queue.task
def translate_subtitles(srt_path, target_language, progress=gr.Progress()):
    progress(0.85, "Translating subtitles...")
    translated_srt_path = srt_path.with_name(srt_path.stem + f'_translated_{target_language}.srt')
    prompt = f"Translate the following SRT file to the target following language or dialect {target_language}"
    with open(srt_path, 'r', encoding='utf-8') as infile:
        for line in infile:
            prompt += line
    srt_word_count = count_srt_words(srt_path)
    # Ratio between tokens and English words is 0.75 I think the it changes from language to language so
    # Assumptions below to support other languages hopefully without issues
    max_tokens_estimated = 4000  # Assuming an average of 4 tokens per word, plus an offset of 500 tokens
    message = anthropic_client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=max_tokens_estimated,
        temperature=0.2,
        system="Return SRT FILE FORMAT !!",
        messages=[
        {"role": "user", "content": prompt} 
    ]
    )
    translated_srt = message.content[0].text
    #Removing extra generated text to preserve SRT Format !!!!!!!!
    #-------------------------------------------------------------#
    translated_srt_lines = (translated_srt.split('\n'))[2:]
    translated_srt = '\n'.join(translated_srt_lines)
    #-------------------------------------------------------------#
    with open(translated_srt_path, 'w', encoding='utf-8') as outfile:
        outfile.write(translated_srt)
    progress(0.9)
    return translated_srt_path


def revising_subtitles(srt_path, progress=gr.Progress()):
    progress(0.7, "Revising subtitles ...")
    revised_srt_path = srt_path.with_name(srt_path.stem + f'_cleaned.srt')
    with open(srt_path, 'r', encoding='utf-8') as infile:
        srt_content = infile.read()

    # Prepare the prompt for the language model
    prompt = f"[[[PRESERVE THE SRT FILE FORMAT !!!]]] FIX WRONG SPELLED WORDS / CONSISTENCY OF THE DIALOGUES OF THE FOLLOWING SRT FILE\n{srt_content}"

    
    srt_word_count = count_srt_words(srt_path)
    # Ratio between tokens and English words is 0.75 I think the it changes from language to language so
    # Assumptions below to support other languages hopefully without issues
    max_tokens_estimated = (srt_word_count * 2) * 4 + 500  # Assuming an average of 4 tokens per word, plus an offset of 500 tokens
    message = anthropic_client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=max_tokens_estimated,
        temperature=0.2,
        system="Respect and preserve SRT file format",
        messages=[
        {"role": "user", "content": prompt} 
    ]
    )
    revised_srt = message.content[0].text
    #Removing extra generated text to preserve SRT Format !!!!!!!!
    #-------------------------------------------------------------#
    revised_srt_lines = (revised_srt.split('\n'))[2:]
    revised_srt = '\n'.join(revised_srt_lines)
    #-------------------------------------------------------------#
    with open(revised_srt_path, 'w', encoding='utf-8') as outfile:
        outfile.write(revised_srt)
    progress(0.9)
    return revised_srt_path

def interface(source_type, youtube_url, file_path, language_sign, target_language):
    output_video = None
    progress = gr.Progress()
    if source_type == "YouTube video":
        if youtube_url and language_sign:
            video_file = download_youtube_video(youtube_url, progress)
            audio_file = extract_audio(video_file, progress)
            srt_path = transcribe_file(audio_file, language_sign,progress)
        else:
            print("Please provide the required inputs.")
            return None
    else:
        if file_path and language_sign:
            uploaded_file_path = Path(file_path.name)
            if uploaded_file_path.suffix.lower() in ['.mp4', '.mkv', '.avi']:
                audio_file = extract_audio(uploaded_file_path, progress)
            else:
                audio_file = uploaded_file_path
            srt_path = transcribe_file(audio_file, language_sign, progress)
        else:
            print("Please provide the required inputs.")
            return None

    if srt_path:
        if target_language:
            translated_srt_path = translate_subtitles(srt_path, target_language, progress)
            if translated_srt_path:
                srt_path = translated_srt_path

        # Merge subtitles with video
        output_video = merge_subtitles(video_file, srt_path, language_sign, progress)

    return output_video

inputs = [
    gr.Radio(choices=["YouTube video", "Local file"], label="Choose the source type:"),
    gr.Textbox(label="Enter the YouTube video link:", placeholder="YouTube URL"),
    gr.File(label="Upload a local file:", file_types=['wav', 'mp3', 'mp4', 'mkv', 'avi']),
    gr.Dropdown(choices=list(LANGUAGE_API_KEYS.keys()), label="Select the language:"),
    gr.Dropdown(choices=['', 'en', 'ar', 'fr', 'ja', 'es', 'de', 'Darija'], label="Select the target language for translation (Optional):")
]

output = gr.Video()

demo = gr.Interface(fn=interface, concurrency_limit=4,inputs=inputs, outputs=output,title="AnaKolchi - Sous Titre Kolchiii")

#demo.queue()  # Set up a queue for the interface
# https://youtu.be/zy8F_tGJYBM?si=65RDzq4JTbm-kzq9
# https://youtu.be/zy8F_tGJYBM?si=65RDzq4JTbm-kzq9
if __name__ == '__main__':
    demo.queue()
    demo.launch(server_name = "0.0.0.0")
