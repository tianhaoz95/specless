import time
import queue
import threading
import sys
import os
import json
import re
from collections import Counter

try:
    from pynput import keyboard
    import sounddevice as sd
    import numpy as np
    from faster_whisper import WhisperModel
    import pyperclip
    import requests
except ImportError as e:
    print(f"Dependencies missing. Please install dependencies using uv. Error: {e}")
    sys.exit(1)

# Configuration
WHISPER_MODEL_SIZE = "tiny.en" # tiny.en is great for POC
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "nemotron-3-nano:4b"

# State
is_recording = False
audio_queue = queue.Queue()
sample_rate = 16000
keyboard_controller = keyboard.Controller()

print(f"Loading Whisper model ({WHISPER_MODEL_SIZE})...")
# Note: On Mac, CPU execution is quite fast for tiny/small models
model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
print("Whisper model loaded.")

JARGON_WORDS = []
jargon_file = os.path.expanduser("~/.specless_jargon.json")
if os.path.exists(jargon_file):
    try:
        with open(jargon_file, 'r') as f:
            JARGON_WORDS = json.load(f)
            print(f"Loaded {len(JARGON_WORDS)} project jargon words.")
    except Exception as e:
        print(f"Failed to load jargon: {e}")

def process_with_llm(raw_text):
    """Sends raw text to local LLM to clean filler words and format."""
    print(f"Raw transcript: '{raw_text}'")
    
    system_prompt = """You are a dictation cleaner. Your ONLY job is to output the final cleaned text.
Rules:
1. Remove all filler words (um, uh, ah).
2. Apply self-corrections logically (e.g. if the user says "order a pizza wait no a burger", output "order a burger").
3. Output ONLY the cleaned text. NO quotes, NO preamble, NO explanations."""
    
    if JARGON_WORDS:
        system_prompt += f"\n4. Project Jargon (DO NOT ALTER THESE SPELLINGS): {', '.join(JARGON_WORDS[:50])}"
    
    try:
        print(f"Waiting for Ollama to process with model '{OLLAMA_MODEL}'...")
        chat_url = OLLAMA_URL.replace("/api/generate", "/api/chat")
        response = requests.post(chat_url, json={
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Raw transcript: 'I want to um order a pizza wait no a burger.'"},
                {"role": "assistant", "content": "I want to order a burger."},
                {"role": "user", "content": "Raw transcript: 'Send the report to ah John no wait send it to Mary.'"},
                {"role": "assistant", "content": "Send the report to Mary."},
                {"role": "user", "content": f"Raw transcript: '{raw_text}'"}
            ],
            "stream": False,
            "options": {
                "num_predict": 128 # Prevent it from generating endlessly
            }
        }, timeout=30)
        
        if response.status_code == 200:
            cleaned_text = response.json().get('message', {}).get('content', '').strip()
            return cleaned_text
        else:
            print(f"LLM Error: {response.status_code} - {response.text}")
            return raw_text
    except requests.exceptions.Timeout:
        print("LLM Error: Request timed out. The model took too long to respond.")
        return raw_text
    except Exception as e:
        print(f"Failed to connect to LLM. Is Ollama running? Error: {e}")
        return raw_text

def audio_callback(indata, frames, time, status):
    """Called for each audio block from the microphone."""
    if is_recording:
        audio_queue.put(indata.copy())

def toggle_recording():
    global is_recording
    if is_recording:
        is_recording = False
        print("\n[Stopped recording] Processing...")
        # Start processing in a new thread so we don't block the hotkey listener
        threading.Thread(target=process_audio).start()
    else:
        # Clear queue
        while not audio_queue.empty():
            audio_queue.get()
        is_recording = True
        print("\n[Started recording] Speak now... Press Ctrl+Cmd+V to stop.")

def process_audio(test_mode=False):
    """Processes the recorded audio chunk."""
    if audio_queue.empty():
        return
        
    print("Converting audio data...")
    audio_data = []
    while not audio_queue.empty():
        audio_data.append(audio_queue.get())
    
    if not audio_data:
        return

    # Flatten and convert to required format (float32, 16kHz)
    audio_np = np.concatenate(audio_data, axis=0)
    audio_np = audio_np.flatten().astype(np.float32)
    
    initial_prompt = None
    if JARGON_WORDS:
        initial_prompt = ", ".join(JARGON_WORDS[:100])
        
    print("Transcribing with Whisper...")
    segments, info = model.transcribe(audio_np, beam_size=5, initial_prompt=initial_prompt)
    
    raw_text = " ".join([segment.text for segment in segments]).strip()
    
    if raw_text:
        print("Sending to local LLM for cleanup...")
        refined_text = process_with_llm(raw_text)
        
        # Fallback to raw text if the LLM hallucinated an empty string
        if not refined_text:
            print("LLM returned an empty string. Falling back to raw transcript.")
            refined_text = raw_text
            
        print(f"Final Refined Text: '{refined_text}'")
        
        # Inject into active application
        print("Injecting text (native AppleScript)...")
        # Give a small delay in case the hotkey release interfered
        time.sleep(0.1)
        
        # 1. Put text on clipboard using native pbcopy
        import subprocess
        process = subprocess.Popen('pbcopy', env={'LANG': 'en_US.UTF-8'}, stdin=subprocess.PIPE)
        process.communicate(refined_text.encode('utf-8'))
        
        # Give clipboard a tiny moment to update
        time.sleep(0.1)
        
        # 2. Tell macOS to press Cmd+V in the frontmost application
        if not test_mode:
            applescript = """
            tell application "System Events"
                keystroke "v" using command down
            end tell
            """
            subprocess.run(['osascript', '-e', applescript])
        else:
            print("Skipping Cmd+V injection because we are in test mode.")
            
        print("Done. Ready for next dictation.")
    else:
        print("No speech detected.")

def index_repository(repo_path):
    print(f"Indexing repository at {repo_path}...")
    
    skip_dirs = {'.git', 'node_modules', 'venv', '.venv', '__pycache__', 'dist', 'build'}
    words_counter = Counter()
    ignore_words = {'if', 'else', 'for', 'while', 'return', 'def', 'class', 'import', 'from', 'as', 'try', 'except', 'with', 'pass', 'break', 'continue', 'and', 'or', 'not', 'is', 'in', 'lambda', 'yield', 'True', 'False', 'None', 'this', 'that', 'var', 'let', 'const', 'function'}
    
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
        
        for file in files:
            if not file.endswith(('.py', '.js', '.ts', '.go', '.rs', '.cpp', '.c', '.h', '.md', '.txt')):
                continue
                
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    tokens = re.findall(r'[A-Za-z_][A-Za-z0-9_]*', content)
                    for token in tokens:
                        if len(token) > 3 and token not in ignore_words:
                            words_counter[token] += 1
            except Exception:
                pass
                
    top_words = [word for word, count in words_counter.most_common(200)]
    
    with open(jargon_file, 'w') as f:
        json.dump(top_words, f)
        
    print(f"Successfully indexed {len(top_words)} jargon words to {jargon_file}!")
    print(f"Top 10: {top_words[:10]} ...")

def check_accessibility_permissions():
    """Checks if macOS Accessibility permissions are granted and prompts user if not."""
    if sys.platform != 'darwin':
        return True
        
    try:
        import ApplicationServices
        import subprocess
        
        # Check if trusted
        is_trusted = ApplicationServices.AXIsProcessTrusted()
        if is_trusted:
            return True
            
        print("Accessibility permissions missing. Prompting user...")
        
        # Native AppleScript dialog
        applescript = """
        display dialog "Specless requires Accessibility permissions to listen for hotkeys and paste text. Would you like to open System Settings now?" buttons {"Cancel", "Open Settings"} default button "Open Settings" with icon caution
        """
        
        result = subprocess.run(['osascript', '-e', applescript], capture_output=True, text=True)
        
        if "Open Settings" in result.stdout:
            # Deep link to Accessibility pane
            subprocess.run(['open', 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'])
            
        print("Exiting due to missing accessibility permissions.")
        sys.exit(1)
        
    except ImportError:
        print("Warning: ApplicationServices module not found. Skipping accessibility check.")
        return True
    except Exception as e:
        print(f"Warning: Failed to check accessibility permissions: {e}")
        return True

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Specless - Local Voice Typing")
    parser.add_argument("--test-audio", type=str, help="Path to a WAV file to process (bypasses microphone)")
    parser.add_argument("--index-repo", type=str, help="Path to a repository to index for jargon")
    args = parser.parse_args()

    if args.index_repo:
        index_repository(args.index_repo)
        return

    if args.test_audio:
        print(f"Running in test mode with audio file: {args.test_audio}")
        import soundfile as sf
        data, samplerate = sf.read(args.test_audio, dtype='float32')
        
        # Resample if not 16kHz (naive resampling, assuming file is close or already 16k for POC)
        if samplerate != sample_rate:
            print(f"Warning: Test audio is {samplerate}Hz, expected {sample_rate}Hz.")
            
        # Convert stereo to mono if needed
        if len(data.shape) > 1:
            data = data.mean(axis=1)
            
        audio_queue.put(data)
        process_audio(test_mode=True)
        return

    # Check for Accessibility permissions before starting listeners
    check_accessibility_permissions()

    print("Starting audio stream...")
    # Setup audio stream
    stream = sd.InputStream(samplerate=sample_rate, channels=1, callback=audio_callback)
    
    print("App is running! Press <Ctrl>+<Cmd>+V to toggle recording.")
    print("Press Ctrl+C in terminal to exit.")
    
    # Setup global hotkey
    hotkey = '<ctrl>+<cmd>+v'
    
    with stream:
        with keyboard.GlobalHotKeys({hotkey: toggle_recording}) as h:
            h.join()

if __name__ == "__main__":
    main()
