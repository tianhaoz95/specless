import time
import queue
import threading
import sys
import os

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

def process_with_llm(raw_text):
    """Sends raw text to local LLM to clean filler words and format."""
    print(f"Raw transcript: '{raw_text}'")
    
    system_prompt = "You are an expert dictation assistant. Take the following raw transcript, remove all filler words (um, uh, like), fix grammar, and handle any self-corrections. Output ONLY the final polished text. Do not include any preamble, quotes or formatting like Markdown."
    
    try:
        print(f"Waiting for Ollama to process with model '{OLLAMA_MODEL}'...")
        chat_url = OLLAMA_URL.replace("/api/generate", "/api/chat")
        response = requests.post(chat_url, json={
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Raw transcript: {raw_text}"}
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

def process_audio():
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
    
    print("Transcribing with Whisper...")
    segments, info = model.transcribe(audio_np, beam_size=5)
    
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
        applescript = """
        tell application "System Events"
            keystroke "v" using command down
        end tell
        """
        subprocess.run(['osascript', '-e', applescript])
            
        print("Done. Ready for next dictation.")
    else:
        print("No speech detected.")

def main():
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
