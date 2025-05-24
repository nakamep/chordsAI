from flask import Flask, request, jsonify
import os
import yt_dlp # For downloading YouTube audio
import numpy as np # For librosa

# --- Library Availability Flags ---
LIBROSA_AVAILABLE = False
PRETTY_MIDI_AVAILABLE = False
app_log_extra = ""

try:
    import librosa
    LIBROSA_AVAILABLE = True
    app_log_extra += "(librosa available) "
except ImportError:
    app_log_extra += "(librosa not available) "

try:
    import pretty_midi
    PRETTY_MIDI_AVAILABLE = True
    app_log_extra += "(pretty_midi available)"
except ImportError:
    app_log_extra += "(pretty_midi not available)"


app = Flask(__name__)
app.logger.info(f"Starting app with library status: {app_log_extra.strip()}")

TEMP_AUDIO_DIR = 'temp_audio'
TEMP_MIDI_DIR = 'static/midi' # MIDI files saved here

# --- Chord to MIDI notes mapping (Helper Function) ---
PITCH_CLASSES = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'Fb': 4, 'E#': 5, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11, 'Cb': 11, 'B#':0}

def get_notes_for_chord(chord_name, base_octave=4):
    if not chord_name or chord_name.lower() == 'n' or chord_name.lower() == 'x': # No chord / Unknown
        return []
    root_str = chord_name[0]
    offset = 1
    if len(chord_name) > 1 and (chord_name[1] == '#' or chord_name[1] == 'b'):
        root_str += chord_name[1]
        offset += 1
    quality_str = chord_name[offset:]
    root_midi_base = PITCH_CLASSES.get(root_str)
    if root_midi_base is None:
        app.logger.warning(f"Unknown root note: {root_str} in chord {chord_name}")
        return []
    root_note = (base_octave + 1) * 12 + root_midi_base
    if root_str in ['A', 'A#', 'Ab', 'B', 'Bb', 'Cb']: # Heuristic to lower common A/B chords by an octave
         root_note -=12
    third, fifth = root_note + 7, None # Perfect fifth is default component
    if 'm' in quality_str.lower() or 'min' in quality_str.lower(): third = root_note + 3
    elif 'dim' in quality_str.lower(): third, fifth = root_note + 3, root_note + 6
    elif 'aug' in quality_str.lower(): third, fifth = root_note + 4, root_note + 8
    else: third = root_note + 4 # Major third for major chords
    return sorted(list(set(filter(None.__ne__, [root_note, third, fifth]))))


# --- MIDI Generation (Helper Function) ---
def create_midi_file_from_chords(chord_list, output_path, chord_duration_s=2.0):
    if not PRETTY_MIDI_AVAILABLE:
        app.logger.warning("PrettyMIDI is not available. Cannot create MIDI file.")
        return None, "PrettyMIDI not available"
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        pm = pretty_midi.PrettyMIDI()
        instrument_program = pretty_midi.instrument_name_to_program('Acoustic Grand Piano')
        piano_instrument = pretty_midi.Instrument(program=instrument_program)
        current_time = 0.0
        for chord_name in chord_list:
            midi_notes = get_notes_for_chord(chord_name)
            if not midi_notes: # Skip 'N' or unparseable chords
                current_time += chord_duration_s
                continue
            for note_number in midi_notes:
                note = pretty_midi.Note(velocity=100, pitch=note_number, start=current_time, end=current_time + chord_duration_s)
                piano_instrument.notes.append(note)
            current_time += chord_duration_s
        pm.instruments.append(piano_instrument)
        pm.write(output_path)
        app.logger.info(f"MIDI file created: {output_path}")
        return output_path, "MIDI file created successfully"
    except Exception as e:
        app.logger.error(f"MIDI creation failed: {e}")
        return None, f"MIDI creation error: {str(e)}"


# --- Librosa Chord Recognition (Helper Function) ---
def get_librosa_chords_from_audio(audio_path_for_librosa, sr=22050, hop_length=512, frame_duration_s=2.0):
    if not LIBROSA_AVAILABLE:
        app.logger.warning("Librosa not available.")
        return [], "Librosa not available"
    try:
        y, sr_loaded = librosa.load(audio_path_for_librosa, sr=sr)
        chroma = librosa.feature.chroma_stft(y=y, sr=sr_loaded, hop_length=hop_length)
        pitches = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        chord_templates = {}
        for i in range(12):
            major_template = np.zeros(12); major_template[i]=1; major_template[(i+4)%12]=1; major_template[(i+7)%12]=1
            chord_templates[pitches[i]] = major_template
            minor_template = np.zeros(12); minor_template[i]=1; minor_template[(i+3)%12]=1; minor_template[(i+7)%12]=1
            chord_templates[pitches[i] + 'm'] = minor_template
        chord_names = list(chord_templates.keys())
        template_matrix = np.array(list(chord_templates.values())).T
        frames_per_segment = int(frame_duration_s * sr_loaded / hop_length)
        num_segments = chroma.shape[1] // frames_per_segment
        recognized_chords_list = []
        if num_segments == 0:
            if chroma.shape[1] > 0:
                mean_chroma = np.mean(chroma, axis=1); similarities = np.dot(mean_chroma, template_matrix)
                recognized_chords_list.append(chord_names[np.argmax(similarities)])
            else: recognized_chords_list.append("N")
        else:
            for i in range(num_segments):
                segment_chroma = chroma[:, i*frames_per_segment:(i+1)*frames_per_segment]
                mean_chroma_segment = np.mean(segment_chroma, axis=1); similarities = np.dot(mean_chroma_segment, template_matrix)
                recognized_chords_list.append(chord_names[np.argmax(similarities)])
        if not recognized_chords_list: return ["N"], "No chords recognized"
        simplified_chords = [recognized_chords_list[0]]
        for chord in recognized_chords_list[1:]:
            if chord != simplified_chords[-1]: simplified_chords.append(chord)
        return simplified_chords, "Librosa processing successful"
    except Exception as e:
        app.logger.error(f"Librosa chord recognition failed: {e}")
        return [], f"Librosa error: {str(e)}"


@app.route('/analyze', methods=['POST'])
def analyze():
    os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)
    os.makedirs(TEMP_MIDI_DIR, exist_ok=True) # Ensure MIDI dir exists
    video_url = "" 
    downloaded_mp3_path = None
    video_id = None # Initialize video_id

    try:
        data = request.get_json()
        if not data or 'url' not in data: return jsonify({"error": "No URL provided"}), 400
        video_url = data['url']

        output_template = os.path.join(TEMP_AUDIO_DIR, '%(id)s.%(ext)s')
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
            'outtmpl': output_template, 'noplaylist': True, 'nocheckcertificate': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=False)
            video_id = info_dict.get('id', None) # Used for MIDI filename
            if not video_id: return jsonify({"error": "Could not extract video ID"}), 500
            expected_mp3_filename = f"{video_id}.mp3"
            downloaded_mp3_path = os.path.join(TEMP_AUDIO_DIR, expected_mp3_filename)
            error_code = ydl.download([video_url])
            if error_code != 0:
                app.logger.error(f"yt-dlp download failed (code {error_code}) for URL: {video_url}")
                return jsonify({"error": "Failed to download audio, yt-dlp error."}), 500
            if not os.path.exists(downloaded_mp3_path):
                app.logger.error(f"Expected mp3 not found at {downloaded_mp3_path} for URL: {video_url}")
                return jsonify({"error": "Audio download succeeded but final mp3 file not found."}), 500
        
        recognized_chords, recognition_method, status_message = [], "None", f"Audio downloaded to {downloaded_mp3_path}"

        # --- Chord Recognition (Librosa only) ---
        if LIBROSA_AVAILABLE:
            app.logger.info(f"Attempting chord recognition with librosa for {downloaded_mp3_path}")
            try:
                chords_from_librosa, librosa_msg = get_librosa_chords_from_audio(downloaded_mp3_path)
                if chords_from_librosa and chords_from_librosa != ["N"]: # Librosa succeeded
                    recognized_chords, recognition_method = chords_from_librosa, "librosa"
                    status_message += f"; Chord recognition complete (librosa: {librosa_msg})"
                    app.logger.info(f"Librosa processing successful for {downloaded_mp3_path}: {librosa_msg}")
                else: # Librosa processed but found no chords or only 'N'
                    status_message += f"; Librosa processed but found no valid chords ({librosa_msg})"
                    app.logger.info(f"Librosa found no valid chords for {downloaded_mp3_path}: {librosa_msg}")
            except Exception as e_librosa:
                app.logger.error(f"Librosa chord recognition failed for {downloaded_mp3_path}: {e_librosa}")
                status_message += f"; Librosa processing failed: {e_librosa}"
        else: # Librosa not available
            app.logger.warning("Librosa is not available for chord recognition.")
            status_message += "; Chord recognition skipped: librosa unavailable."
            
        # --- MIDI Generation ---
        midi_file_path_for_response = None
        if recognized_chords and video_id: # video_id should be available if download succeeded
            if PRETTY_MIDI_AVAILABLE:
                midi_filename = f"{video_id}_chords.mid"
                full_midi_output_path = os.path.join(TEMP_MIDI_DIR, midi_filename)
                path_or_none, midi_msg = create_midi_file_from_chords(recognized_chords, full_midi_output_path)
                if path_or_none: midi_file_path_for_response = path_or_none # This is like 'static/midi/video_id.mid'
                status_message += f"; {midi_msg}"
            else: status_message += "; MIDI generation skipped: PrettyMIDI not available."
        elif not recognized_chords: status_message += "; MIDI generation skipped: No chords recognized."
            
        return jsonify({
            "message": status_message, "audio_path": downloaded_mp3_path,
            "chords": recognized_chords, "recognition_method": recognition_method,
            "midi_file_path": midi_file_path_for_response
        })

    except yt_dlp.utils.DownloadError as e: return jsonify({"error": "yt-dlp DownloadError.", "details": str(e)}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error in /analyze for URL '{video_url}': {str(e)}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred.", "details": str(e)}), 500
    finally:
        if downloaded_mp3_path and os.path.exists(downloaded_mp3_path):
            try: os.remove(downloaded_mp3_path); app.logger.info(f"Cleaned up: {downloaded_mp3_path}")
            except Exception as e: app.logger.error(f"Error cleaning {downloaded_mp3_path}: {e}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
