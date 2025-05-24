# YouTube Chord Extractor & MIDI Generator (chordsAI)

A web application that downloads audio from YouTube videos, analyzes the audio to recognize chord progressions, and generates a corresponding MIDI file.

## Features

*   Downloads audio from YouTube URLs.
*   Recognizes chord progressions from the audio.
    *   Primarily uses `madmom` for chord recognition (if available).
    *   Includes a fallback mechanism using `librosa` if `madmom` is not installed or fails.
*   Generates a downloadable MIDI file based on the recognized chords.
*   Simple, single-page web interface for URL input and results display.

## Tech Stack

*   **Frontend:** React (via CDN in a single HTML file), Tailwind CSS (via CDN).
*   **Backend:** Python, Flask.
*   **Core Python Libraries:**
    *   `yt-dlp`: For downloading audio from YouTube.
    *   `madmom`: For advanced chord recognition.
    *   `librosa`: For audio processing and chord recognition fallback.
    *   `pretty_midi`: For generating MIDI files.
    *   `Flask`: Web framework for the backend API.
    *   `Cython`, `numpy`, `scipy`: Essential libraries for scientific computing and dependencies for the core audio libraries.

## Prerequisites

Before you begin, ensure you have the following installed:

1.  **Python:** Version 3.10 or newer. You can download it from [python.org](https://www.python.org/).
2.  **pip:** Python package installer (usually comes with Python).
3.  **FFmpeg:** This is crucial for `yt-dlp` to extract and convert audio (e.g., to MP3).
    *   Download FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html).
    *   Ensure the `ffmpeg` (and `ffprobe`) executable is in your system's PATH or accessible by `yt-dlp`.
4.  **Git (Optional):** For cloning the repository. Otherwise, you can download the source code as a ZIP file.
5.  **A C Compiler (for `madmom`):** If you intend for `madmom` to install successfully (it's optional, as the app has a fallback), you'll need a C compiler.
    *   **Linux:** Typically `gcc` (e.g., `sudo apt-get install build-essential python3-dev`).
    *   **macOS:** Xcode Command Line Tools (e.g., `xcode-select --install`).
    *   **Windows:** Build Tools for Visual Studio (select "C++ build tools" during installation).

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
    *   **Install Cython and NumPy:** These are critical build dependencies for `madmom` and should be installed before other packages.
        ```bash
        pip install Cython numpy
        ```
    *   **Install all other dependencies:**
        ```bash
        pip install -r requirements.txt
        ```
    *   **Note on `madmom` Installation:** `madmom` provides high-quality chord recognition but can be challenging to install due to its C extensions. If it fails to install (even with Cython and NumPy pre-installed and a C compiler available), the application will automatically fall back to using `librosa` for chord recognition. The core functionality will still work.
    *   **FFmpeg Reminder:** Double-check that FFmpeg is installed and accessible in your system's PATH. `yt-dlp` will not be able to process audio effectively without it.

3.  **Frontend Setup:**
    *   The frontend is a single HTML file located at `frontend/index.html`.
    *   **No build step is required.** It uses CDNs for React, Tailwind CSS, and Babel.

## Running the Application

1.  **Start the Backend Server:**
    *   Ensure your Python virtual environment (`venv`) is activated.
    *   From the project's root directory, run the Flask application:
        ```bash
        python app.py
        ```
    *   The backend server will start, typically on `http://localhost:5000`. You should see log messages in your terminal, including the availability status of `madmom`, `librosa`, and `pretty_midi`.

2.  **Launch the Frontend:**
    *   Open the `frontend/index.html` file directly in your web browser (e.g., by double-clicking it or using "File > Open" in your browser).

## How to Use

1.  Once the backend is running and `frontend/index.html` is open in your browser:
2.  Enter a valid YouTube video URL into the input field.
3.  Click the "Extract Chords & Generate MIDI" button.
4.  Wait for processing. A loading indicator will be shown. This may take some time depending on the video.
5.  **Results will be displayed:**
    *   A status message indicating the outcome.
    *   The list of recognized chords and the method used (e.g., "madmom" or "librosa").
    *   A download link for the generated MIDI file (if successful).
6.  If an error occurs, an error message will be shown.

## Troubleshooting

*   **`madmom` fails to install:** The application is designed to fall back to `librosa`. Ensure `Cython` and `numpy` were installed *before* `pip install -r requirements.txt`. If `madmom` is critical for you, ensure you have the necessary C compiler and Python development headers for your OS.
*   **Errors related to "ffmpeg" or "ffprobe":** This means `yt-dlp` cannot find FFmpeg. Verify your FFmpeg installation and that its directory is in your system's PATH.
*   **Frontend shows "Error: Failed to fetch" or similar:**
    *   Ensure the Flask backend server (`python app.py`) is running.
    *   Check the terminal where you ran `python app.py` for any error messages from the backend.
    *   Verify your browser can access `http://localhost:5000`.
*   **Virtual environment issues:** Ensure your virtual environment is activated before running `pip install` or `python app.py`.

This README provides a comprehensive guide for users.
```
