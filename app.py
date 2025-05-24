from flask import Flask, request, jsonify
import os
import yt_dlp
import numpy as np

# Attempt to import madmom modules
try:
    from madmom.features.chords import DBNChordRecognitionProcessor, CRFChordRecognitionProcessor
    from madmom.audio.signal import Signal
    MADMOM_AVAILABLE = True
    app_log_extra = "(madmom available)"
except ImportError:
    MADMOM_AVAILABLE = False
    app_log_extra = "(madmom not available, will use librosa fallback)"

# Import librosa for fallback
try:
    import librosa
    LIBROSA_AVAILABLE = True
    app_log_extra += " (librosa available)"
except ImportError:
    LIBROSA_AVAILABLE = False
    app_log_extra += " (librosa not available)"

# Import pretty_midi for MIDI generation
try:
    import pretty_midi
    PRETTY_MIDI_AVAILABLE = True
    app_log_extra += " (pretty_midi available)"
except ImportError:
    PRETTY_MIDI_AVAILABLE = False
    app_log_extra += " (pretty_midi not available)"

app = Flask(__name__)
app.logger.info(f"Starting app {app_log_extra}")

TEMP_AUDIO_DIR = 'temp_audio'
TEMP_MIDI_DIR = 'static/midi' # MIDI files saved here, accessible via /static/midi/filename.mid

# --- Chord to MIDI notes mapping ---
PITCH_CLASSES = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'Fb': 4, 'E#': 5, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11, 'Cb': 11, 'B#':0}

def get_notes_for_chord(chord_name, base_octave=4):
    """
    Parses a chord name and returns a list of MIDI note numbers for its triad.
    E.g., "C" -> [60, 64, 67], "Am" -> [57, 60, 64] (for base_octave=4)
    """
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

    root_note = (base_octave + 1) * 12 + root_midi_base # Default C4=60

    # Adjust octave to ensure it's not too low. C4 is 60. A3 is 57.
    # If root is C, C# etc, this is fine. If A, A#, B, they might be too high, let's try one octave lower as default.
    # A common convention is for chord roots to be around C3-C4.
    # Let's make C4 the default root, and adjust if it seems too high for common chords like Am.
    # A4 = 69. Am = A3, C4, E4 => 57, 60, 64.
    # If root_str is A or B, maybe use octave-1?
    if root_str in ['A', 'A#', 'Ab', 'B', 'Bb', 'Cb']:
         root_note -=12


    third = None
    fifth = root_note + 7 # Perfect fifth

    if 'm' in quality_str.lower() or 'min' in quality_str.lower(): # minor
        third = root_note + 3 # Minor third
    elif 'dim' in quality_str.lower(): # diminished
        third = root_note + 3 # Minor third
        fifth = root_note + 6 # Diminished fifth
    elif 'aug' in quality_str.lower(): # augmented
        third = root_note + 4 # Major third
        fifth = root_note + 8 # Augmented fifth
    else: # Major (default)
        third = root_note + 4 # Major third

    return sorted(list(set(filter(None, [root_note, third, fifth]))))


# --- MIDI Generation ---
def create_midi_file(chord_list, output_filename_with_path, chord_duration_s=2.0):
    """
    Creates a MIDI file from a list of chord names.
    Assumes each chord has a fixed duration.
    """
    if not PRETTY_MIDI_AVAILABLE:
        app.logger.warning("PrettyMIDI is not available. Cannot create MIDI file.")
        return None, "PrettyMIDI not available"
    
    try:
        # Ensure output directory exists
        output_dir = os.path.dirname(output_filename_with_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        pm = pretty_midi.PrettyMIDI()
        instrument_program = pretty_midi.instrument_name_to_program('Acoustic Grand Piano')
        piano_instrument = pretty_midi.Instrument(program=instrument_program)
        
        current_time = 0.0
        for chord_name in chord_list:
            midi_notes = get_notes_for_chord(chord_name)
            if not midi_notes: # Skip if chord is 'N' or unparseable
                current_time += chord_duration_s # Still advance time
                continue

            for note_number in midi_notes:
                note = pretty_midi.Note(
                    velocity=100, 
                    pitch=note_number, 
                    start=current_time, 
                    end=current_time + chord_duration_s
                )
                piano_instrument.notes.append(note)
            current_time += chord_duration_s
            
        pm.instruments.append(piano_instrument)
        pm.write(output_filename_with_path)
        app.logger.info(f"MIDI file created: {output_filename_with_path}")
        return output_filename_with_path, "MIDI file created successfully"

    except Exception as e:
        app.logger.error(f"MIDI creation failed: {e}")
        return None, f"MIDI creation error: {str(e)}"

# --- Librosa Chord Recognition Fallback ---
def get_librosa_chords(audio_path, sr=22050, hop_length=512, frame_duration_s=2.0):
    if not LIBROSA_AVAILABLE:
        app.logger.warning("Librosa is not available. Cannot perform chord recognition.")
        return [], "Librosa not available"
    try:
        y, sr = librosa.load(audio_path, sr=sr)
        chroma = librosa.feature.chroma_stft(y=y, sr=sr, hop_length=hop_length)
        pitches = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        chord_templates = {}
        for i in range(12):
            major_template = np.zeros(12); major_template[i]=1; major_template[(i+4)%12]=1; major_template[(i+7)%12]=1
            chord_templates[pitches[i]] = major_template # Store major chords as "C", "D", etc.
            minor_template = np.zeros(12); minor_template[i]=1; minor_template[(i+3)%12]=1; minor_template[(i+7)%12]=1
            chord_templates[pitches[i] + 'm'] = minor_template # Store minor chords as "Cm", "Dm", etc.
        
        chord_names = list(chord_templates.keys())
        template_matrix = np.array(list(chord_templates.values())).T
        frames_per_segment = int(frame_duration_s * sr / hop_length)
        num_segments = chroma.shape[1] // frames_per_segment
        recognized_chords_list = []

        if num_segments == 0:
            if chroma.shape[1] > 0:
                mean_chroma = np.mean(chroma, axis=1)
                similarities = np.dot(mean_chroma, template_matrix)
                best_chord_idx = np.argmax(similarities)
                recognized_chords_list.append(chord_names[best_chord_idx])
            else:
                 recognized_chords_list.append("N")
        else:
            for i in range(num_segments):
                segment_chroma = chroma[:, i*frames_per_segment : (i+1)*frames_per_segment]
                mean_chroma_segment = np.mean(segment_chroma, axis=1)
                similarities = np.dot(mean_chroma_segment, template_matrix)
                best_chord_idx = np.argmax(similarities)
                recognized_chords_list.append(chord_names[best_chord_idx])
        
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
    # Ensure temp directories exist
    for temp_dir in [TEMP_AUDIO_DIR, TEMP_MIDI_DIR]:
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

    audio_path = None
    midi_file_path_for_response = None
    recognized_chords = []
    status_message = "Analysis initiated"

    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({"error": "No URL provided"}), 400
        
        video_url = data['url']
        video_id = video_url.split("v=")[-1].split("&")[0] # Basic ID, consider more robust extraction
        safe_filename_base = "".join(c if c.isalnum() else "_" for c in video_id)
        output_template = os.path.join(TEMP_AUDIO_DIR, f'{safe_filename_base}.%(ext)s')

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
            'nocheckcertificate': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            error_code = ydl.download([video_url])
            if error_code != 0: return jsonify({"error": "Failed to download audio"}), 500
        
        audio_path = os.path.join(TEMP_AUDIO_DIR, f'{safe_filename_base}.mp3')
        if not os.path.exists(audio_path):
            found_files = [f for f in os.listdir(TEMP_AUDIO_DIR) if f.startswith(safe_filename_base) and not f.endswith(".part")]
            if not found_files: return jsonify({"error": "Failed to download audio or find downloaded file"}), 500
            audio_path = os.path.join(TEMP_AUDIO_DIR, found_files[0])
        
        status_message = f"Audio downloaded to {audio_path}"

        # Chord recognition
        if MADMOM_AVAILABLE:
            app.logger.info("Attempting chord recognition with madmom.")
            try:
                sig = Signal(audio_path) # Madmom might need specific sample rate or mono
                dbn_proc = DBNChordRecognitionProcessor()
                dbn_chords_data = dbn_proc(sig)
                crf_proc = CRFChordRecognitionProcessor()
                chords_data = crf_proc(dbn_chords_data)
                # Madmom output: [[start, end, chord_label], ...]
                # For MIDI generation, we'd ideally use these start/end times.
                # For now, just extracting labels as per previous setup.
                recognized_chords = [item[2] for item in chords_data if len(item) == 3 and item[2].lower() != 'n']
                status_message = "Chord recognition complete (madmom)"
                app.logger.info("Madmom processing successful.")
            except Exception as e:
                app.logger.error(f"Madmom chord recognition failed: {e}. Will attempt librosa fallback.")
                status_message = f"Madmom failed: {e}. Trying librosa."
                if LIBROSA_AVAILABLE:
                    recognized_chords, librosa_status = get_librosa_chords(audio_path)
                    status_message = f"Chord recognition attempted (librosa fallback after madmom error: {librosa_status})"
                    app.logger.info(f"Librosa fallback attempt status: {librosa_status}")
                else:
                    app.logger.warning("Librosa not available for fallback after madmom error.")
                    status_message = "Madmom failed, and Librosa fallback is not available."
        
        elif LIBROSA_AVAILABLE:
            app.logger.info("Madmom not available. Attempting chord recognition with librosa.")
            recognized_chords, librosa_status = get_librosa_chords(audio_path)
            status_message = f"Chord recognition complete (librosa: {librosa_status})"
            app.logger.info(f"Librosa processing status: {librosa_status}")
        
        else:
            app.logger.warning("Neither madmom nor librosa are available for chord recognition.")
            status_message = "Chord recognition skipped: madmom and librosa unavailable."
            recognized_chords = []

        # MIDI Generation
        if recognized_chords and PRETTY_MIDI_AVAILABLE:
            app.logger.info(f"Attempting MIDI generation for chords: {recognized_chords}")
            midi_filename = f"{safe_filename_base}_chords.mid"
            full_midi_output_path = os.path.join(TEMP_MIDI_DIR, midi_filename)
            
            _, midi_status = create_midi_file(recognized_chords, full_midi_output_path)
            if _ : # If path is returned (success)
                midi_file_path_for_response = full_midi_output_path # e.g. static/midi/videoID_chords.mid
                status_message += f"; {midi_status}"
                app.logger.info(f"MIDI generation status: {midi_status}")
            else: # MIDI creation failed
                status_message += f"; MIDI generation failed: {midi_status}"
                app.logger.warning(f"MIDI generation failed: {midi_status}")
        elif not recognized_chords:
            status_message += "; No chords recognized to generate MIDI."
            app.logger.info("No chords recognized, skipping MIDI generation.")
        elif not PRETTY_MIDI_AVAILABLE:
            status_message += "; PrettyMIDI not available to generate MIDI."
            app.logger.warning("PrettyMIDI not available, skipping MIDI generation.")


        return jsonify({
            "message": status_message,
            "audio_path": audio_path,
            "chords": recognized_chords,
            "midi_file_path": midi_file_path_for_response
        })

    except Exception as e:
        app.logger.error(f"Error in /analyze endpoint: {e}", exc_info=True) # Log traceback
        error_response = {"error": f"An unexpected error occurred: {str(e)}"}
        if audio_path and os.path.exists(audio_path):
            error_response["audio_path"] = audio_path
        return jsonify(error_response), 500
    finally:
        # Clean up the downloaded audio file
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                app.logger.info(f"Cleaned up temporary audio file: {audio_path}")
            except Exception as e_clean:
                app.logger.error(f"Error cleaning up audio file {audio_path}: {e_clean}")

if __name__ == '__main__':
    for temp_dir in [TEMP_AUDIO_DIR, TEMP_MIDI_DIR]: # Ensure dirs exist at startup
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
    app.run(debug=True, host='0.0.0.0', port=5000)
