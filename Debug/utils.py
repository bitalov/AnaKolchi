import subprocess
from pathlib import Path
import re
import os
from tafrigh import Config, TranscriptType, farrigh
import anthropic

def download_youtube_video(youtube_url, progress, output_text):
    output_text.insert("Downloading YouTube video...", "\n")
    progress.update(value=0.25)

    output_path = Path('downloads') / '%(id)s.%(ext)s'
    command = ['yt-dlp', '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4', '-o', str(output_path), youtube_url]
    subprocess.run(command, check=True)
    video_file = next(Path('downloads').glob('*.mp4'))

    progress.update(value=0.3)
    return video_file

def extract_audio(file_path, progress, output_text):
    output_text.insert("Extracting audio from video...", "\n")
    progress.update(value=0.3)

    audio_output_path = file_path.with_suffix('.wav')
    command = ['ffmpeg', '-i', str(file_path), '-vn', '-acodec', 'pcm_s16le', '-ar', '22050', '-ac', '1', str(audio_output_path)]
    subprocess.run(command, check=True)

    progress.update(value=0.5)
    return audio_output_path

def clean_srt_file(srt_path, progress):
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

    progress.update(value=0.9)
    return cleaned_srt_path

def merge_subtitles(video_path, srt_path, language, progress, output_text):
    output_text.insert("Merging subtitles with video...", "\n")
    progress.update(value=0.95)

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

    progress.update(value=1.0)
    return output_path

def is_wav_file(file_path):
    try:
        with open(file_path, 'rb') as file:
            return file.read(4) == b'RIFF'
    except IOError:
        return False

def transcribe_file(file_path, language_sign, progress, output_text):
    output_text.insert("Transcribing audio file...", "\n")
    progress.update(value=0.5)

    if not is_wav_file(file_path):
        output_text.insert(f"Skipping file {file_path} as it is not in WAV format.", "\n")
        return None

    wit_api_key = LANGUAGE_API_KEYS.get(language_sign.upper())
    if not wit_api_key:
        output_text.insert(f"API key not found for language: {language_sign}", "\n")
        return None

    config = Config(
        urls_or_paths=[str(file_path)],
        skip_if_output_exist=False,
        playlist_items="",
        verbose=False,
        model_name_or_path="small",
        task="",
        language="",
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
    progress.update(value=0.9)

    srt_file = Path(os.path.join(str(file_path.parent), f"{file_path.stem}.srt"))
    txt_file = Path(os.path.join(str(file_path.parent), f"{file_path.stem}.txt"))

    if srt_file.exists() and srt_file.stat().st_size > 0 and txt_file.exists() and txt_file.stat().st_size > 0:
        output_text.insert("Transcription completed. Check the links below for the generated files.", "\n")
        return srt_file
    else:
        output_text.insert("Transcription failed. No SRT or TXT file was generated, or the files are corrupted.", "\n")

    return None

def count_srt_words(srt_path):
    with open(srt_path, 'r', encoding='utf-8') as infile:
        content = infile.read()
        return len(content.split())

def translate_subtitles(srt_path, target_language, progress, output_text):
    output_text.insert("Translating subtitles...", "\n")
    progress.update(value=0.85)
    translated_srt_path = srt_path.with_name(srt_path.stem + f'_translated_{target_language}.srt')
    prompt = f"Translate the following SRT file to the target following language or dialect {target_language}"
    with open(srt_path, 'r', encoding='utf-8') as infile:
        for line in infile:
            prompt += line
    srt_word_count = count_srt_words(srt_path)
    max_tokens_estimated = (srt_word_count * 2) * 4 + 500
    message = anthropic_client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=max_tokens_estimated,
        temperature=0.2,
        system="Detect what's language / Dialect automatically and respect and preserve SRT file format",
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
    progress.update(value = 90)
    return translated_srt_path