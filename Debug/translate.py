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
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

anthropic_client = anthropic.Anthropic(
    api_key=ANTHROPIC_API_KEY,
)



def count_srt_words(srt_path):
    with open(srt_path, 'r', encoding='utf-8') as infile:
        content = infile.read()
    return len(content.split())

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

srt_path = Path(r"C:\Users\bilal\OneDrive\Desktop\AnaKolchi\downloads\mNDj_YT971A.srt")
language = "EN"  # Specify the language code
output_path = translate_subtitles_debug(srt_path, language)
# Print the output path
print("Translated Subtitles saved at:", output_path)
sys.exit(0)