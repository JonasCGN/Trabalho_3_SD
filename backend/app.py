from flask import Flask, request, jsonify, send_file
import os
import uuid
import sqlite3
import json
import cv2
from datetime import datetime
import hashlib
import mimetypes
import subprocess
import numpy as np

app = Flask(__name__)

MEDIA_ROOT = "media"
DATABASE_PATH = "data/videos.db"

def init_database():
    # Criar diretório de dados se não existir
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    os.makedirs(MEDIA_ROOT, exist_ok=True)
    if not os.path.exists(DATABASE_PATH):
       open(DATABASE_PATH, 'w').close()        
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            original_name TEXT,
            original_ext TEXT,
            mime_type TEXT,
            size_bytes INTEGER,
            duration_sec REAL,
            fps REAL,
            width INTEGER,
            height INTEGER,
            filter TEXT,
            created_at TEXT,
            path_original TEXT,
            path_processed TEXT
        )
    ''')
    conn.commit()
    conn.close()

def create_directory_structure(video_id, date_obj):
    year = date_obj.strftime('%Y')
    month = date_obj.strftime('%m')
    day = date_obj.strftime('%d')
    
    base_path = os.path.join(MEDIA_ROOT, "videos", year, month, day, video_id)
    
    os.makedirs(os.path.join(base_path, "original"), exist_ok=True)
    os.makedirs(os.path.join(base_path, "processed"), exist_ok=True)
    os.makedirs(os.path.join(base_path, "thumbs"), exist_ok=True)
    os.makedirs(os.path.join(MEDIA_ROOT, "incoming"), exist_ok=True)
    
    return base_path

def get_video_info(video_path):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = frame_count / fps if fps > 0 else 0
    cap.release()
    return duration, fps, width, height

def apply_filter(input_path, output_path, filter_type):
    # Passo 1: Extrair áudio do vídeo original
    temp_audio_path = output_path.replace('.mp4', '_temp_audio.aac')
    temp_video_path = output_path.replace('.mp4', '_temp_video.mp4')
    
    # Extrair áudio usando ffmpeg
    audio_extract_cmd = [
        'ffmpeg', '-i', input_path, '-vn', '-acodec', 'copy', 
        temp_audio_path, '-y'
    ]
    
    try:
        subprocess.run(audio_extract_cmd, check=True, capture_output=True)
        has_audio = True
    except subprocess.CalledProcessError:
        # Se falhar, o vídeo pode não ter áudio
        has_audio = False
    
    # Passo 2: Processar vídeo com OpenCV (mantendo seu código atual)
    cap = cv2.VideoCapture(input_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(temp_video_path, fourcc, fps, (width, height))
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        if filter_type == 'grayscale':
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        elif filter_type == 'blur':
            frame = cv2.GaussianBlur(frame, (15, 15), 0)
        elif filter_type == 'edge':
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 100, 200)
            frame = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        elif filter_type == 'brightness':
            frame = cv2.convertScaleAbs(frame, alpha=1.0, beta=50)
        elif filter_type == 'sepia':
            # Filtro sepia usando transformação de matriz
            kernel = np.array([[0.272, 0.534, 0.131],
                              [0.349, 0.686, 0.168],
                              [0.393, 0.769, 0.189]])
            frame = cv2.transform(frame, kernel)
        
        out.write(frame)
    
    cap.release()
    out.release()
    
    # Passo 3: Combinar áudio e vídeo usando ffmpeg
    if has_audio:
        # Juntar vídeo processado com áudio original
        combine_cmd = [
            'ffmpeg', '-i', temp_video_path, '-i', temp_audio_path,
            '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental',
            output_path, '-y'
        ]
        
        try:
            subprocess.run(combine_cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"Erro ao combinar áudio e vídeo: {e}")
            # Se falhar, pelo menos mantenha o vídeo sem áudio
            os.rename(temp_video_path, output_path)
    else:
        # Se não há áudio, apenas renomeie o vídeo processado
        os.rename(temp_video_path, output_path)
    
    # Limpar arquivos temporários
    if os.path.exists(temp_audio_path):
        os.remove(temp_audio_path)
    if os.path.exists(temp_video_path):
        os.remove(temp_video_path)

def generate_thumbnail(video_path, thumb_path):
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    if ret:
        # Resize to thumbnail size
        height, width = frame.shape[:2]
        max_size = 150
        if width > height:
            new_width = max_size
            new_height = int(height * max_size / width)
        else:
            new_height = max_size
            new_width = int(width * max_size / height)
        
        thumbnail = cv2.resize(frame, (new_width, new_height))
        cv2.imwrite(thumb_path, thumbnail)
    cap.release()

@app.route('/upload', methods=['POST'])
def upload_video():
    file = request.files['video']
    filter_type = request.form['filter']
    
    video_id = str(uuid.uuid4())
    created_at = datetime.now()
    
    # Save to incoming
    original_name, original_ext = os.path.splitext(file.filename)
    temp_path = os.path.join(MEDIA_ROOT, "incoming", f"{video_id}{original_ext}")
    os.makedirs(os.path.join(MEDIA_ROOT, "incoming"), exist_ok=True)
    file.save(temp_path)
    
    # Create structure
    base_path = create_directory_structure(video_id, created_at)
    
    # Move to final location
    original_path = os.path.join(base_path, "original", f"video{original_ext}")
    os.rename(temp_path, original_path)
    
    # Get video info
    duration, fps, width, height = get_video_info(original_path)
    size_bytes = os.path.getsize(original_path)
    mime_type = mimetypes.guess_type(original_path)[0]
    
    # Apply filter
    os.makedirs(os.path.join(base_path, "processed", filter_type), exist_ok=True)
    processed_path = os.path.join(base_path, "processed", filter_type, f"video{original_ext}")
    apply_filter(original_path, processed_path, filter_type)
    
    # Generate thumbnails for both original and processed
    thumb_original_path = os.path.join(base_path, "thumbs", "original.jpg")
    thumb_processed_path = os.path.join(base_path, "thumbs", "processed.jpg")
    
    generate_thumbnail(original_path, thumb_original_path)
    generate_thumbnail(processed_path, thumb_processed_path)
    
    # Create metadata
    metadata = {
        'id': video_id,
        'original_name': original_name,
        'filter': filter_type,
        'created_at': created_at.isoformat(),
        'checksum': hashlib.md5(open(original_path, 'rb').read()).hexdigest()
    }
    
    with open(os.path.join(base_path, "meta.json"), 'w') as f:
        json.dump(metadata, f)
    
    # Save to database
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO videos VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (video_id, original_name, original_ext, mime_type, size_bytes,
          duration, fps, width, height, filter_type, created_at.isoformat(),
          original_path, processed_path))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'video_id': video_id})

@app.route('/videos', methods=['GET'])
def list_videos():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM videos ORDER BY created_at DESC')
    videos = cursor.fetchall()
    conn.close()
    
    return jsonify({'videos': videos})

@app.route('/videos/<video_id>', methods=['GET'])
def get_video(video_id):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM videos WHERE id LIKE ?', (f'{video_id}%',))
    video = cursor.fetchone()
    conn.close()
    
    if video:
        return jsonify({'video': video})
    return jsonify({'error': 'Video not found'}), 404

@app.route('/download/<video_id>', methods=['GET'])
def download_video(video_id):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT path_processed FROM videos WHERE id LIKE ?', (f'{video_id}%',))
    result = cursor.fetchone()
    conn.close()
    
    if result and os.path.exists(result[0]):
        return send_file(result[0], as_attachment=True)
    return jsonify({'error': 'Video not found'}), 404

@app.route('/download/<video_id>/original', methods=['GET'])
def download_original_video(video_id):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT path_original FROM videos WHERE id LIKE ?', (f'{video_id}%',))
    result = cursor.fetchone()
    conn.close()
    
    if result and os.path.exists(result[0]):
        return send_file(result[0], as_attachment=True)
    return jsonify({'error': 'Original video not found'}), 404

@app.route('/thumbnail/<video_id>/<thumb_type>', methods=['GET'])
def get_thumbnail(video_id, thumb_type):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT path_original FROM videos WHERE id LIKE ?', (f'{video_id}%',))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        original_path = result[0]
        base_path = os.path.dirname(os.path.dirname(original_path))
        
        thumb_paths = []
        if thumb_type == 'original':
            thumb_paths = [
                os.path.join(base_path, "thumbs", "original.jpg"),
                os.path.join(base_path, "thumbs", "frame_0001.jpg")
            ]
        elif thumb_type == 'processed':
            thumb_paths = [
                os.path.join(base_path, "thumbs", "processed.jpg"),
                os.path.join(base_path, "thumbs", "frame_0001.jpg")
            ]
        
        for thumb_path in thumb_paths:
            if os.path.exists(thumb_path):
                return send_file(thumb_path)
    
    return jsonify({'error': 'Thumbnail not found'}), 404

@app.route('/', methods=['GET'])
def index():
    return jsonify({'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    init_database()
    app.run(host='0.0.0.0', port=9981, debug=False)
