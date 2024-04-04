#Implementing and Debugging translation function before merging ....

import sys
import re
import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from tafrigh import Config, TranscriptType, farrigh
import anthropic

load_dotenv()

LANGUAGE_API_KEYS = {
    'AR': os.getenv('WIT_API_KEY_ARABIC'),
    'EN': os.getenv('WIT_API_KEY_ENGLISH'),
    'FR': os.getenv('WIT_API_KEY_FRENCH'),
    'JA': os.getenv('WIT_API_KEY_JAPANESE'),
    # Add more languages and API keys as needed
}
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

anthropic_client = anthropic.Anthropic(
    api_key=ANTHROPIC_API_KEY,
)



def count_srt_words(srt_content):
    # Split the content by lines
    lines = srt_content.split('\n')
    word_count = 0

    # Iterate over the lines and count words in subtitle lines only
    for line in lines:
        if line and not line.isdigit() and '-->' not in line:
            word_count += len(line.split())

    return word_count

def translate_subtitles_debug(srt_path, target_language):
    #st.text("Translating subtitles...")
    #progress_bar.progress(85)
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
        system="Detect what's language / Dialect automaticaly and Respect and preserve SRT file format. Start with Content of the SRT File Directly to respect the format",
        messages=[
        {"role": "user", "content": prompt} 
    ]
    )
    translated_srt = message.content[0].text
    translated_srt_lines = (translated_srt.split('\n'))[2:]
    translated_srt = '\n'.join(translated_srt_lines)
    with open(translated_srt_path, 'w', encoding='utf-8') as outfile:
        outfile.write(translated_srt)
    #progress_bar.progress(90)
    return translated_srt_path

def revising_subtitles(srt_path):
    revised_srt_path = srt_path.with_name(srt_path.stem + '_cleaned.srt')

    # Read the entire SRT file content
    with open(srt_path, 'r', encoding='utf-8') as infile:
        srt_content = infile.read()

    # Prepare the prompt for the language model
    prompt = f"[[[PRESERVE THE SRT FILE FORMAT !!!]]] FIX WRONG SPELLED WORDS / CONSISTENCY OF THE DIALOGUES OF THE FOLLOWING SRT FILE\n{srt_content}"

    # Estimate the maximum number of tokens needed for the language model
    srt_word_count = count_srt_words(srt_content)
    max_tokens_estimated = (srt_word_count * 2) * 4 + 500  # Assuming an average of 4 tokens per word, plus an offset of 500 tokens

    # Send the prompt to the language model and get the revised SRT content
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

    # Remove extra generated text to preserve SRT format
    revised_srt_lines = revised_srt.split('\n')[2:]
    revised_srt = '\n'.join(revised_srt_lines)

    # Write the revised SRT content to a new file
    with open(revised_srt_path, 'w', encoding='utf-8') as outfile:
        outfile.write(revised_srt)

    return revised_srt_path

def transcribe_file(file_path, language_sign):

    wit_api_key = LANGUAGE_API_KEYS.get(language_sign.upper())
    if not wit_api_key:
        print(f"API key not found for language: {language_sign}")
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

    srt_file = Path(os.path.join(str(file_path.parent), f"{file_path.stem}.srt"))
    txt_file = Path(os.path.join(str(file_path.parent), f"{file_path.stem}.txt"))

    if srt_file.exists() and srt_file.stat().st_size > 0 and txt_file.exists() and txt_file.stat().st_size > 0:
        #print("Transcription completed. Check the links below for the generated files.")
        #cleaned_srt_file = clean_srt_file(srt_file, progress_bar)
        return srt_file
    else:
        print("Transcription failed. No SRT or TXT file was generated, or the files are corrupted.")

    return None


if __name__ == '__main__':
    # Example usage
    audio_path = Path(r"C:\Users\bilal\OneDrive\Desktop\AnaKolchi\downloads\KdYDAVL5tOg.wav")
    language = "en"  # Language sign
    #output_path = transcribe_file(audio_path, language)
    cleaned = revising_subtitles(Path(r"C:\Users\bilal\OneDrive\Desktop\AnaKolchi\downloads\KdYDAVL5tOg.srt"))
    #if output_path:
        #print(f"Transcription completed. Output file: {output_path}")