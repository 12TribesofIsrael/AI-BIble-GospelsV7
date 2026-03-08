#!/usr/bin/env python3
"""
Biblical Text Processor for Bible Chapter Video Generator
Automatically limits input text to 1000 words maximum for optimal video generation.

Usage: Run the script and paste your biblical text when prompted.
Output: Processed text ready for n8n workflow input.
"""

import re
import sys
import os

def clean_text(text):
    """Clean and normalize the input text."""
    # Remove extra whitespace and normalize line breaks
    text = re.sub(r'\n+', ' ', text)  # Replace multiple newlines with spaces
    text = re.sub(r'\s+', ' ', text.strip())  # Replace multiple spaces with single space
    
    # Remove verse references like "Deuteronomy 4:7-8" but keep the actual text
    text = re.sub(r'\b[A-Za-z]+\s+\d+:\d+(-\d+)?\s+', '', text)
    
    # Remove standalone numbers at the beginning of sentences (verse numbers)
    text = re.sub(r'\s+\d+\s+', ' ', text)
    
    # Clean up punctuation spacing
    text = re.sub(r'([.!?])\s*', r'\1 ', text)
    
    # Remove multiple spaces again
    text = re.sub(r'\s+', ' ', text)
    
    # Remove section headers and precept references
    text = re.sub(r'Precepts to [^:]+:', '', text)
    text = re.sub(r'How special and Holy they are', '', text)
    text = re.sub(r'THE MOST HIGH CHOSEN PEOPLE', '', text)
    
    return text.strip()

def split_into_words(text):
    """Split text into individual words."""
    return text.split()

def limit_to_words(words, max_words=1000):
    """Limit the word list to maximum number of words."""
    if len(words) <= max_words:
        return words
    
    truncated = words[:max_words]
    text_so_far = ' '.join(truncated)
    
    # Find last complete sentence
    last_period = text_so_far.rfind('.')
    last_exclamation = text_so_far.rfind('!')
    last_question = text_so_far.rfind('?')
    last_sentence_end = max(last_period, last_exclamation, last_question)
    
    if last_sentence_end > 0:
        clean_text_end = text_so_far[:last_sentence_end + 1]
        return clean_text_end.split()
    
    return truncated

def format_output(words):
    """Format the final output text."""
    text = ' '.join(words)
    sentences = re.split(r'([.!?])', text)
    formatted_sentences = []
    sentence_count = 0
    
    for i in range(0, len(sentences) - 1, 2):
        if i + 1 < len(sentences):
            sentence = sentences[i] + sentences[i + 1]
            formatted_sentences.append(sentence.strip())
            sentence_count += 1
            
            if sentence_count % 2 == 0:
                formatted_sentences.append('\n')
    
    return ''.join(formatted_sentences).strip()

def read_input_file():
    """Read content from the Input file."""
    input_file = "Input"
    
    if not os.path.exists(input_file):
        print(f"❌ Error: '{input_file}' file not found!")
        print("   Please make sure the 'Input' file exists in the current directory.")
        return None
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        print(f"❌ Error reading '{input_file}': {e}")
        return None

def main():
    print("=" * 60)
    print("📖 BIBLICAL TEXT PROCESSOR FOR VIDEO GENERATION")
    print("=" * 60)
    print("🎯 Automatically limits text to 1000 words maximum")
    print("📹 Optimized for 20-scene biblical video generation")
    print("⏱️  Generates 5-7 minute videos at 150 WPM")
    print("-" * 60)
    
    print("\n📂 Reading biblical text from 'Input' file...")
    
    # Read from Input file
    raw_text = read_input_file()
    if raw_text is None:
        return
    
    print("✅ Successfully loaded text from Input file")
    print(f"📄 Raw text length: {len(raw_text)} characters")
    
    print("\n🔄 Processing text...")
    
    cleaned_text = clean_text(raw_text)
    words = cleaned_text.split()
    
    print(f"📊 Original word count: {len(words)} words")
    
    if len(words) == 0:
        print("❌ No words found after cleaning. The text may need manual review.")
        print("📝 Raw text preview:")
        print(raw_text[:200] + "..." if len(raw_text) > 200 else raw_text)
        return
    
    limited_words = limit_to_words(words, max_words=1000)
    final_text = format_output(limited_words)
    
    word_count = len(limited_words)
    expected_minutes = word_count / 150
    expected_scenes = word_count // 40
    
    print(f"✅ Processed word count: {word_count} words")
    print(f"🎬 Expected video length: {expected_minutes:.1f} minutes")
    print(f"🎭 Expected scenes: {expected_scenes} scenes")
    
    if len(words) > 1000:
        print(f"✂️  Text truncated from {len(words)} to {word_count} words")
    
    print("\n" + "=" * 60)
    print("📋 PROCESSED TEXT (Ready for n8n workflow):")
    print("=" * 60)
    print(final_text)
    print("=" * 60)
    
    print(f"\n💡 Copy the text above and paste it into your n8n workflow")
    print(f"🎯 This will generate approximately {expected_minutes:.1f} minutes of video")
    
    # Automatically save processed text to file
    filename = f"processed_biblical_text_{word_count}words.txt"
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(final_text)
        print(f"\n💾 ✅ Processed text automatically saved to: {filename}")
    except Exception as e:
        print(f"\n💾 ❌ Error saving file: {e}")

if __name__ == "__main__":
    main() 