# YouTube Chord Extractor & MIDI Generator (chordsAI)

A web application that downloads audio from YouTube videos, analyzes the audio to recognize chord progressions using `librosa`, and generates a corresponding MIDI file.

## Features

*   Downloads audio from YouTube URLs.
*   Recognizes chord progressions from the audio using `librosa`.
*   Generates a downloadable MIDI file based on the recognized chords.
*   Simple, single-page web interface for URL input and results display.

## Tech Stack

*   **Frontend:** React (via CDN in a single HTML file), Tailwind CSS (via CDN).
*   **Backend:** Python, Flask.
*   **Core Python Libraries:**
    *   `yt-dlp`: For downloading audio from YouTube.
    *   `librosa`: For audio processing and chord recognition.
    *   `pretty_midi`: For generating MIDI files.
    *   `Flask`: Web framework for the backend API.
    *   `numpy`, `scipy`: Essential libraries for scientific computing and dependencies for `librosa`.

## Prerequisites

Before you begin, ensure you have the following installed:

1.  **Python:** Version 3.10 or newer. You can download it from [python.org](https://www.python.org/).
2.  **pip:** Python package installer (usually comes with Python).
3.  **FFmpeg:** Required by `yt-dlp` for audio processing.
    *   **Local Development:** Ensure it's installed on your system and accessible via the PATH. You can download it from [ffmpeg.org](https://ffmpeg.org/download.html).
    *   **Railway Deployment:** FFmpeg is automatically installed during the build process via the `nixpacks.toml` configuration file included in this repository.
4.  **Git (Optional):** For cloning the repository. Otherwise, you can download the source code as a ZIP file.

## Setup and Installation

1.  **Clone the Repository (or Download Source):**
    ```bash
    git clone <repository_url>
    cd <repository_name> 
    ```
    (Replace `<repository_url>` and `<repository_name>` with actual values). If downloaded as a ZIP, extract and navigate to the root directory.

2.  **Backend Setup:**
    *   **Navigate to the project's root directory.**
    *   **Create a Python virtual environment:** This isolates project dependencies.
        ```bash
        python -m venv venv
        ```
    *   **Activate the virtual environment:**
        *   On Windows: `venv\Scripts\activate`
        *   On macOS/Linux: `source venv/bin/activate`
        (Your terminal prompt should now show `(venv)`.)
    *   **Install Python dependencies:**
        ```bash
        pip install -r requirements.txt
        ```
    *   **FFmpeg Reminder (Local Development):** For local development, double-check that FFmpeg is installed and accessible in your system's PATH. `yt-dlp` will not be able to process audio effectively without it. (For Railway, see Prerequisites).

3.  **Frontend Setup:**
    *   The frontend is a single HTML file located at `static/index.html`.
    *   **No build step is required.** It uses CDNs for React, Tailwind CSS, and Babel.

## Running the Application

1.  **Start the Backend Server:**
    *   Ensure your Python virtual environment (`venv`) is activated.
    *   From the project's root directory, run the Flask application:
        ```bash
        python app.py
        ```
    *   The backend server will start, typically on `http://localhost:5000`. You should see log messages in your terminal, including the availability status of `librosa` and `pretty_midi`.
    *   **Note on Port Configuration:**
        When running `python app.py` locally, the application defaults to port 5000.
        When deployed to platforms like Railway, the application will automatically use the port number specified by the `PORT` environment variable set by the platform.

2.  **Launch the Frontend:**
    *   After starting the backend server, open your web browser and navigate to the Flask server's address (typically `http://localhost:5000/`).

## Deployment to Railway (or similar platforms)

Deploying this application to platforms like Railway involves specifying how the platform should build and run the application.

**Using `build.sh` (Optional Custom Build Control):**
This repository includes a `build.sh` script. This script primarily upgrades `pip`, `setuptools`, and `wheel`, and then installs dependencies from `requirements.txt` using `pip install -r requirements.txt --no-cache-dir`. The `--no-cache-dir` flag ensures fresh package downloads, which can be beneficial in CI/CD environments.

While not strictly necessary for this simplified project (as `pip install -r requirements.txt` is often a default build command on many platforms), you can use `build.sh` for more explicit control over the build process if needed.

**To use `build.sh` on Railway:**

1.  In your Railway project settings, navigate to the **Settings** tab, then find the **Build** section.
2.  Locate the **Build Command** field.
3.  Set the `Build Command` to:
    ```bash
    bash build.sh
    ```
4.  Ensure your **Root Directory** setting in Railway (if applicable) correctly points to the root of your repository.

For more general information on build configurations on Railway, refer to their official documentation:
(See Railway's documentation for more details: https://docs.railway.com/guides/builds#build-command )

The included `nixpacks.toml` file handles the installation of system dependencies like FFmpeg on Railway, ensuring it's available for the application.

## How to Use

1.  Once the backend is running, open your web browser and navigate to the Flask server's address (typically `http://localhost:5000/`).
2.  Enter a valid YouTube video URL into the input field.
3.  Click the "Extract Chords & Generate MIDI" button.
4.  Wait for processing. A loading indicator will be shown. This may take some time depending on the video.
5.  **Results will be displayed:**
    *   A status message indicating the outcome.
    *   The list of recognized chords (using `librosa`).
    *   A download link for the generated MIDI file (if successful).
6.  If an error occurs, an error message will be shown.

## Troubleshooting

*   **Errors related to "ffmpeg" or "ffprobe" (Local Development):** This means `yt-dlp` cannot find FFmpeg. Verify your FFmpeg installation and that its directory is in your system's PATH. (For Railway, FFmpeg is handled by `nixpacks.toml`).
*   **Frontend shows "Error: Failed to fetch" or similar:**
    *   Ensure the Flask backend server (`python app.py`) is running.
    *   Check the terminal where you ran `python app.py` for any error messages from the backend.
    *   Verify your browser can access `http://localhost:5000` (or your deployment URL).
*   **Virtual environment issues:** Ensure your virtual environment is activated before running `pip install` or `python app.py` locally.

This README provides a comprehensive guide for users.
```
