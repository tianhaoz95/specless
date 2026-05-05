import subprocess
import pyperclip
import time
import os

def test_specless_pipeline():
    # 1. Clear the clipboard so we know it's not a false positive
    pyperclip.copy("")
    
    # 2. Run the main script in test mode
    workspace_dir = "/Users/tianhaozhou/github/specless"
    wav_path = os.path.join(workspace_dir, "tests/fixtures/test_audio.wav")
    
    assert os.path.exists(wav_path), f"Test fixture {wav_path} is missing!"
    
    print(f"Running main.py with {wav_path}...")
    # Use uv run to execute it
    result = subprocess.run(
        ["uv", "run", "main.py", "--test-audio", wav_path],
        cwd=workspace_dir,
        capture_output=True,
        text=True
    )
    
    print("--- STDOUT ---")
    print(result.stdout)
    if result.stderr:
        print("--- STDERR ---")
        print(result.stderr)
        
    assert result.returncode == 0, "The application crashed during the pipeline execution."
    
    # 3. Verify the clipboard contents
    # We expect the LLM to have cleaned up "I want to um order a pizza wait no a burger."
    # to something like "I want to order a burger."
    final_clipboard = pyperclip.paste()
    
    print(f"Final Clipboard content: '{final_clipboard}'")
    
    assert final_clipboard != "", "Clipboard is empty! The LLM failed to return text or pbcopy failed."
    
    lower_clipboard = final_clipboard.lower()
    assert "burger" in lower_clipboard, "The final text did not contain the corrected word 'burger'."
    assert "pizza" not in lower_clipboard, "The LLM failed to handle the self-correction (kept 'pizza')."
    assert "um" not in lower_clipboard, "The LLM failed to remove the filler word ('um')."
