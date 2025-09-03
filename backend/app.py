from flask import Flask, request, jsonify, send_file, render_template_string
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

# Template HTML para a interface web
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Video Processing System</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: Arial, sans-serif;
            background-color: #f5f5f5;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .header h1 {
            color: #333;
            margin-bottom: 10px;
        }
        
        .header p {
            color: #666;
        }
        
        .stats {
            display: flex;
            justify-content: center;
            gap: 30px;
            margin: 20px 0;
            flex-wrap: wrap;
        }
        
        .stat-item {
            text-align: center;
        }
        
        .stat-number {
            font-size: 2em;
            font-weight: bold;
            color: #007bff;
        }
        
        .stat-label {
            color: #666;
            margin-top: 5px;
        }
        
        .videos-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        
        .video-card {
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
            transition: transform 0.3s ease;
        }
        
        .video-card:hover {
            transform: translateY(-5px);
        }
        
        .video-thumbnail {
            width: 100%;
            height: 200px;
            background-color: #f0f0f0;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow: hidden;
        }
        
        .video-thumbnail img {
            max-width: 100%;
            max-height: 100%;
            object-fit: cover;
        }
        
        .video-thumbnail .no-thumb {
            color: #999;
            font-size: 3em;
        }
        
        .filter-badge {
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(0, 123, 255, 0.9);
            color: white;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 0.8em;
            text-transform: capitalize;
        }
        
        .video-info {
            padding: 15px;
        }
        
        .video-title {
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
            font-size: 1.1em;
        }
        
        .video-details {
            color: #666;
            font-size: 0.9em;
            margin-bottom: 15px;
        }
        
        .video-details div {
            margin-bottom: 5px;
        }
        
        .video-actions {
            display: flex;
            gap: 10px;
        }
        
        .btn {
            padding: 8px 15px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            text-decoration: none;
            font-size: 0.9em;
            transition: background-color 0.3s ease;
            display: inline-block;
            text-align: center;
        }
        
        .btn-primary {
            background-color: #007bff;
            color: white;
        }
        
        .btn-primary:hover {
            background-color: #0056b3;
        }
        
        .btn-secondary {
            background-color: #6c757d;
            color: white;
        }
        
        .btn-secondary:hover {
            background-color: #545b62;
        }
        
        .no-videos {
            text-align: center;
            padding: 50px;
            color: #666;
        }
        
        .no-videos i {
            font-size: 4em;
            margin-bottom: 20px;
            color: #ddd;
        }
        
        @media (max-width: 768px) {
            .videos-grid {
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            }
            
            .stats {
                gap: 15px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎬 Sistema de Processamento de Vídeos</h1>
            <p>Visualize e gerencie seus vídeos processados</p>
            
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-number">{{ total_videos }}</div>
                    <div class="stat-label">Total de Vídeos</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{{ total_filters }}</div>
                    <div class="stat-label">Filtros Únicos</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{{ total_size_mb }}MB</div>
                    <div class="stat-label">Espaço Utilizado</div>
                </div>
            </div>
        </div>
        
        {% if videos %}
        <div class="videos-grid">
            {% for video in videos %}
            <div class="video-card">
                <div class="video-thumbnail">
                    <img src="/thumbnail/{{ video[0] }}/processed" 
                         alt="Thumbnail do vídeo {{ video[1] }}"
                         onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">
                    <div class="no-thumb" style="display: none;">🎥</div>
                    <div class="filter-badge">{{ video[9] }}</div>
                </div>
                <div class="video-info">
                    <div class="video-title">{{ video[1] }}{{ video[2] }}</div>
                    <div class="video-details">
                        <div><strong>Duração:</strong> {{ "%.1f"|format(video[5]) }}s</div>
                        <div><strong>Resolução:</strong> {{ video[7] }}x{{ video[8] }}</div>
                        <div><strong>Tamanho:</strong> {{ "%.1f"|format(video[4]/1024/1024) }}MB</div>
                        <div><strong>Criado em:</strong> {{ video[10][:19].replace('T', ' ') }}</div>
                    </div>
                    <div>
                        <p>Downloads</p>
                        <div class="video-actions">
                            <a href="/download/{{ video[0] }}" class="btn btn-primary">📥 Filtro</a>
                            <a href="/download/{{ video[0] }}/original" class="btn btn-secondary">📄 Original</a>
                        </div>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <div class="no-videos">
            <div>📹</div>
            <h3>Nenhum vídeo encontrado</h3>
            <p>Faça upload de um vídeo para começar!</p>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET'])
def index():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Buscar todos os vídeos
    cursor.execute('SELECT * FROM videos ORDER BY created_at DESC')
    videos = cursor.fetchall()
    
    # Calcular estatísticas
    cursor.execute('SELECT COUNT(*) FROM videos')
    total_videos = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT filter) FROM videos')
    total_filters = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(size_bytes) FROM videos')
    total_size = cursor.fetchone()[0] or 0
    total_size_mb = round(total_size / 1024 / 1024, 1)
    
    conn.close()
    
    return render_template_string(HTML_TEMPLATE, 
                                videos=videos,
                                total_videos=total_videos,
                                total_filters=total_filters,
                                total_size_mb=total_size_mb)

if __name__ == '__main__':
    init_database()
    app.run(host='0.0.0.0', port=9981, debug=False)
