class Specless < Formula
  desc "Specless: Local AI Voice Typing Assistant"
  homepage "https://github.com/tianhaoz95/specless"
  
  # For a real release, this would point to a tarball of the PyInstaller binary
  # Example: url "https://github.com/tianhaoz95/specless/releases/download/v0.1.0/specless-mac.tar.gz"
  url "https://example.com/placeholder.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  version "0.1.0"

  def install
    # Install the pre-compiled binary into the homebrew bin directory
    bin.install "specless"
  end

  # This service block is the magic that creates the macOS LaunchAgent (.plist)
  # It ensures the app runs in the background and starts on boot.
  service do
    run opt_bin/"specless"
    keep_alive true
    log_path var/"log/specless.log"
    error_log_path var/"log/specless_error.log"
    # Ensure it only runs when a user is logged in (needed for UI/clipboard access)
    run_type :mac_os
  end

  def caveats
    <<~EOS
      Specless relies on Accessibility and Microphone permissions to function.
      
      Since you installed it via Homebrew Services, it runs in the background. 
      You MUST grant Accessibility and Microphone permissions to '/usr/sbin/smbd' 
      or '/bin/bash' (depending on macOS version and how launchd runs it) or manually 
      whitelist the installed binary:
      
      #{opt_bin}/specless
      
      To start the background service immediately and on login, run:
        brew services start specless
    EOS
  end
end
