# Publishing Specless

Follow these instructions to officially publish your local application so that any macOS user can install it via Homebrew and run it as a background service.

## 1. Create a GitHub Release
First, you need to compile the application and upload the binary to your main repository's Releases page.

1. **Build the Binary:**
   Open a terminal in this project directory and run:
   ```bash
   ./build.sh
   ```
   *This creates a standalone executable at `dist/specless`.*

2. **Compress the Binary:**
   Homebrew expects a compressed archive.
   ```bash
   cd dist
   tar -czvf specless-mac-arm64.tar.gz specless
   ```

3. **Get the SHA256 Hash:**
   You will need the cryptographic hash of this tarball for the Homebrew formula.
   ```bash
   shasum -a 256 specless-mac-arm64.tar.gz
   ```
   *(Copy the output string, you will need it shortly).*

4. **Upload to GitHub:**
   - Go to your repository on GitHub: `https://github.com/tianhaoz95/specless`
   - Click **Releases** > **Draft a new release**.
   - Create a new tag (e.g., `v0.1.0`).
   - Drag and drop `dist/specless-mac-arm64.tar.gz` into the attached binaries section.
   - Click **Publish release**.
   - Right-click the `.tar.gz` file link on the published release page and select **Copy Link Address**.

## 2. Create the Homebrew Tap
Homebrew Taps are simply GitHub repositories with a specific naming convention.

1. **Create the Tap Repository:**
   Create a new public repository on GitHub named exactly: `homebrew-specless`
   *(This allows users to install via `brew tap tianhaoz95/specless`)*

2. **Update the Formula:**
   Open `specless.rb` from this project and update the following lines:
   - Replace the `url` string with the copied link from your GitHub Release.
   - Replace the `sha256` string with the hash you generated earlier.
   - Update the `version` if necessary.

3. **Push to the Tap:**
   Copy your updated `specless.rb` file into the new `homebrew-specless` repository and push it to the `main` branch.

## 3. Test the Installation
To verify everything works smoothly from an end-user perspective:

```bash
# Add your custom tap
brew tap tianhaoz95/specless

# Install the binary
brew install specless

# Start the background service (which will also ask for Accessibility permissions)
brew services start specless
```
