from flask import Flask, request, jsonify, send_from_directory
import os
import numpy as np # For librosa
import requests # For downloading from URL
from werkzeug.utils import secure_filename # For uploaded filenames
import uuid # For unique filenames from URLs
import re # For parsing Content-Disposition if needed, though might not use initially

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

@app.route('/')
def serve_index():
    return send_from_directory('static', 'index.html')

TEMP_AUDIO_DIR = 'temp_audio'
TEMP_MIDI_DIR = 'static/midi'

# --- Chord to MIDI notes mapping (Helper Function) ---
PITCH_CLASSES = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'Fb': 4, 'E#': 5, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11, 'Cb': 11, 'B#':0}
def get_notes_for_chord(chord_name, base_octave=4):
    if not chord_name or chord_name.lower() == 'n' or chord_name.lower() == 'x': return []
    root_str = chord_name[0]; offset = 1
    if len(chord_name) > 1 and (chord_name[1] == '#' or chord_name[1] == 'b'): root_str += chord_name[1]; offset += 1
    quality_str = chord_name[offset:]; root_midi_base = PITCH_CLASSES.get(root_str)
    if root_midi_base is None: app.logger.warning(f"Unknown root: {root_str} in {chord_name}"); return []
    root_note = (base_octave + 1) * 12 + root_midi_base
    if root_str in ['A', 'A#', 'Ab', 'B', 'Bb', 'Cb']: root_note -=12
    third, fifth = root_note + 7, None
    if 'm' in quality_str.lower() or 'min' in quality_str.lower(): third = root_note + 3
    elif 'dim' in quality_str.lower(): third, fifth = root_note + 3, root_note + 6
    elif 'aug' in quality_str.lower(): third, fifth = root_note + 4, root_note + 8
    else: third = root_note + 4
    return sorted(list(set(filter(None.__ne__, [root_note, third, fifth]))))

# --- MIDI Generation (Helper Function) ---
def create_midi_file_from_chords(chord_list, output_path, chord_duration_s=2.0):
    if not PRETTY_MIDI_AVAILABLE: return None, "PrettyMIDI not available"
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        pm = pretty_midi.PrettyMIDI(); piano_instrument = pretty_midi.Instrument(program=pretty_midi.instrument_name_to_program('Acoustic Grand Piano'))
        current_time = 0.0
        for chord_name in chord_list:
            midi_notes = get_notes_for_chord(chord_name)
            if not midi_notes: current_time += chord_duration_s; continue
            for note_number in midi_notes:
                piano_instrument.notes.append(pretty_midi.Note(velocity=100, pitch=note_number, start=current_time, end=current_time + chord_duration_s))
            current_time += chord_duration_s
        pm.instruments.append(piano_instrument); pm.write(output_path)
        app.logger.info(f"MIDI created: {output_path}")
        return output_path, "MIDI file created successfully"
    except Exception as e: app.logger.error(f"MIDI creation failed: {e}"); return None, f"MIDI error: {str(e)}"

# --- Librosa Chord Recognition (Helper Function) ---
def get_librosa_chords_from_audio(audio_path_for_librosa, sr=22050, hop_length=512, frame_duration_s=2.0):
    if not LIBROSA_AVAILABLE: return [], "Librosa not available"
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
        chord_names = list(chord_templates.keys()); template_matrix = np.array(list(chord_templates.values())).T
        frames_per_segment = int(frame_duration_s * sr_loaded / hop_length); num_segments = chroma.shape[1] // frames_per_segment
        recognized_chords_list = []
        if num_segments == 0:
            if chroma.shape[1] > 0: mean_chroma = np.mean(chroma, axis=1); similarities = np.dot(mean_chroma, template_matrix); recognized_chords_list.append(chord_names[np.argmax(similarities)])
            else: recognized_chords_list.append("N")
        else:
            for i in range(num_segments):
                segment_chroma = chroma[:, i*frames_per_segment:(i+1)*frames_per_segment]
                mean_chroma_segment = np.mean(segment_chroma, axis=1); similarities = np.dot(mean_chroma_segment, template_matrix); recognized_chords_list.append(chord_names[np.argmax(similarities)])
        if not recognized_chords_list: return ["N"], "No chords recognized"
        simplified_chords = [recognized_chords_list[0]]
        for chord in recognized_chords_list[1:]:
            if chord != simplified_chords[-1]: simplified_chords.append(chord)
        return simplified_chords, "Librosa processing successful"
    except Exception as e: app.logger.error(f"Librosa chord recognition failed: {e}"); return [], f"Librosa error: {str(e)}"

@app.route('/analyze', methods=['POST'])
def analyze():
    os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)
    os.makedirs(TEMP_MIDI_DIR, exist_ok=True)
    
    audio_path = None
    file_id_for_midi = None # Used for naming MIDI file, derived from filename or uuid
    status_message = "Analysis initiated"

    try:
        audio_file = request.files.get('audio_file')
        audio_url = request.form.get('audio_url')

        if audio_file and audio_file.filename != '':
            app.logger.info(f"Processing uploaded file: {audio_file.filename}")
            filename = secure_filename(audio_file.filename)
            audio_path = os.path.join(TEMP_AUDIO_DIR, filename)
            audio_file.save(audio_path)
            file_id_for_midi, _ = os.path.splitext(filename) # Use filename (without ext) for MIDI name
            status_message = f"Uploaded file '{filename}' processed."
        
        elif audio_url:
            app.logger.info(f"Processing audio from URL: {audio_url}")
            try:
                response = requests.get(audio_url, stream=True, timeout=20) # Increased timeout
                response.raise_for_status()
                
                # Attempt to get filename from Content-Disposition or URL
                url_filename_part = ""
                cd = response.headers.get('content-disposition')
                if cd:
                    fname_match = re.search('filename="?([^"]+)"?', cd)
                    if fname_match:
                        url_filename_part = secure_filename(fname_match.group(1))
                
                if not url_filename_part: # Fallback to part of URL
                    url_filename_part = audio_url.split('/')[-1].split('?')[0]
                    if not url_filename_part or len(url_filename_part) > 64: # Avoid overly long names
                        url_filename_part = "downloaded_audio"

                _, ext = os.path.splitext(url_filename_part)
                if not ext or len(ext) > 5 : ext = ".mp3" # Default to .mp3 if no/bad extension

                unique_id = str(uuid.uuid4())
                unique_filename = f"{unique_id}{ext}"
                audio_path = os.path.join(TEMP_AUDIO_DIR, secure_filename(unique_filename))
                
                with open(audio_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                file_id_for_midi = unique_id # Use UUID for MIDI name to ensure uniqueness
                status_message = f"Audio downloaded from URL and saved as '{unique_filename}'."

            except requests.exceptions.RequestException as e:
                app.logger.error(f"Error downloading from URL {audio_url}: {e}")
                return jsonify({"error": "Failed to download audio from URL.", "details": str(e)}), 400
            except Exception as e: # Catch other errors during download/saving
                app.logger.error(f"Error processing URL {audio_url}: {e}", exc_info=True)
                return jsonify({"error": "An unexpected error occurred processing the URL.", "details": str(e)}), 500
        else:
            return jsonify({"error": "No audio file or URL provided."}), 400

        # --- Chord Recognition (Librosa only) ---
        recognized_chords, recognition_method = [], "None"
        if LIBROSA_AVAILABLE:
            app.logger.info(f"Attempting librosa for {audio_path}")
            try:
                chords_from_librosa, librosa_msg = get_librosa_chords_from_audio(audio_path)
                if chords_from_librosa and chords_from_librosa != ["N"]:
                    recognized_chords, recognition_method = chords_from_librosa, "librosa"
                    status_message += f"; Chord recognition complete (librosa: {librosa_msg})"
                else: status_message += f"; Librosa processed but found no valid chords ({librosa_msg})"
            except Exception as e: status_message += f"; Librosa processing failed: {e}"
        else: status_message += "; Chord recognition skipped: librosa unavailable."
            
        # --- MIDI Generation ---
        midi_file_path_for_response = None
        if recognized_chords and file_id_for_midi:
            if PRETTY_MIDI_AVAILABLE:
                midi_filename = f"{file_id_for_midi}_chords.mid"
                full_midi_output_path = os.path.join(TEMP_MIDI_DIR, midi_filename)
                path_or_none, midi_msg = create_midi_file_from_chords(recognized_chords, full_midi_output_path)
                if path_or_none: midi_file_path_for_response = path_or_none
                status_message += f"; {midi_msg}"
            else: status_message += "; MIDI generation skipped: PrettyMIDI not available."
        elif not recognized_chords: status_message += "; MIDI generation skipped: No chords recognized."
            
        return jsonify({
            "message": status_message, "processed_audio_filename": os.path.basename(audio_path) if audio_path else None,
            "chords": recognized_chords, "recognition_method": recognition_method,
            "midi_file_path": midi_file_path_for_response
        })

    except Exception as e:
        app.logger.error(f"Unexpected error in /analyze: {str(e)}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred.", "details": str(e)}), 500
    finally:
        if audio_path and os.path.exists(audio_path):
            try: os.remove(audio_path); app.logger.info(f"Cleaned up: {audio_path}")
            except Exception as e: app.logger.error(f"Error cleaning {audio_path}: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
