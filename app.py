#!/usr/bin/env python3
"""
TikTok Clipper - Interface Web
Application Flask pour découper des vidéos YouTube en clips
"""

from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import os
import sys
from pathlib import Path
import yt_dlp
from moviepy.editor import VideoFileClip
import math
import threading
import time
import uuid
import shutil
import zipfile

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

# Stockage des tâches en cours
tasks = {}

class TikTokClipper:
    def __init__(self, task_id, output_dir="clips_output"):
        self.task_id = task_id
        self.output_dir = Path(output_dir) / task_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.status = "starting"
        self.progress = 0
        self.message = "Initialisation..."
        self.clips = []
        
    def update_status(self, status, progress, message):
        """Met à jour le statut de la tâche"""
        self.status = status
        self.progress = progress
        self.message = message
        tasks[self.task_id] = {
            'status': status,
            'progress': progress,
            'message': message,
            'clips': [str(c.name) for c in self.clips]
        }
        
    def download_video(self, youtube_url):
        """Télécharge une vidéo YouTube"""
        self.update_status("downloading", 10, "Téléchargement de la vidéo...")
        
        ydl_opts = {
            'format': 'best[height<=1080]',
            'outtmpl': str(self.output_dir / 'temp_video.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'web'],
                    'skip': ['hls', 'dash']
                }
            },
            'http_headers': {
                'User-Agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip',
                'Accept-Language': 'en-US,en;q=0.9',
            }
        }       
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
                video_title = info['title']
                filename = ydl.prepare_filename(info)
                self.update_status("downloaded", 30, f"Téléchargé: {video_title}")
                return filename, video_title
        except Exception as e:
            self.update_status("error", 0, f"Erreur téléchargement: {str(e)}")
            return None, None
    
    def resize_to_tiktok_format(self, clip):
        """Redimensionne le clip au format TikTok 9:16 (1080x1920)"""
        target_width = 1080
        target_height = 1920
        
        # Obtenir les dimensions actuelles
        w, h = clip.size
        
        # Calculer le ratio actuel et le ratio cible
        current_ratio = w / h
        target_ratio = target_width / target_height
        
        if current_ratio > target_ratio:
            # Vidéo trop large : on crop horizontalement
            new_width = int(h * target_ratio)
            x_center = w / 2
            x1 = int(x_center - new_width / 2)
            clip = clip.crop(x1=x1, width=new_width)
        else:
            # Vidéo trop haute : on crop verticalement
            new_height = int(w / target_ratio)
            y_center = h / 2
            y1 = int(y_center - new_height / 2)
            clip = clip.crop(y1=y1, height=new_height)
        
        # Redimensionner à la taille exacte TikTok
        clip = clip.resize((target_width, target_height))
        
        return clip
    
    def cut_video_into_clips(self, video_path, clip_duration=65):
        """Découpe la vidéo en clips au format TikTok 9:16"""
        self.update_status("processing", 40, "Analyse de la vidéo...")
        
        try:
            video = VideoFileClip(video_path)
            total_duration = video.duration
            num_clips = math.ceil(total_duration / clip_duration)
            
            self.update_status("processing", 50, f"Création de {num_clips} clips (format 9:16)...")
            
            for i in range(num_clips):
                start_time = i * clip_duration
                end_time = min((i + 1) * clip_duration, total_duration)
                
                if end_time - start_time < 30:
                    continue
                
                progress = 50 + int((i / num_clips) * 45)
                self.update_status("processing", progress, f"Création clip {i+1}/{num_clips} (format TikTok)...")
                
                clip = video.subclip(start_time, end_time)
                
                # Redimensionner au format TikTok 9:16
                clip = self.resize_to_tiktok_format(clip)
                
                output_path = self.output_dir / f"clip_{i+1:03d}.mp4"
                
                clip.write_videofile(
                    str(output_path),
                    codec='libx264',
                    audio_codec='aac',
                    fps=30,
                    verbose=False,
                    logger=None
                )
                
                self.clips.append(output_path)
            
            video.close()
            return self.clips
            
        except Exception as e:
            self.update_status("error", 0, f"Erreur découpage: {str(e)}")
            return []
    
    def process_video(self, youtube_url, clip_duration=65):
        """Processus complet"""
        try:
            # Télécharger
            video_path, title = self.download_video(youtube_url)
            if not video_path:
                return
            
            # Découper
            clips = self.cut_video_into_clips(video_path, clip_duration)
            
            # Nettoyage
            if os.path.exists(video_path):
                os.remove(video_path)
            
            self.update_status("completed", 100, f"✅ {len(clips)} clips créés!")
            
        except Exception as e:
            self.update_status("error", 0, f"Erreur: {str(e)}")


def process_video_task(task_id, youtube_url, clip_duration):
    """Fonction exécutée en arrière-plan"""
    clipper = TikTokClipper(task_id)
    clipper.process_video(youtube_url, clip_duration)


@app.route('/')
def index():
    """Page d'accueil"""
    return render_template('index.html')


@app.route('/api/process', methods=['POST'])
def process():
    """Lance le traitement d'une vidéo"""
    data = request.json
    youtube_url = data.get('url')
    clip_duration = int(data.get('duration', 65))
    
    if not youtube_url:
        return jsonify({'error': 'URL manquante'}), 400
    
    # Créer une tâche unique
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        'status': 'starting',
        'progress': 0,
        'message': 'Initialisation...',
        'clips': []
    }
    
    # Lancer en arrière-plan
    thread = threading.Thread(
        target=process_video_task,
        args=(task_id, youtube_url, clip_duration)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({'task_id': task_id})


@app.route('/api/status/<task_id>')
def get_status(task_id):
    """Récupère le statut d'une tâche"""
    if task_id not in tasks:
        return jsonify({'error': 'Tâche introuvable'}), 404
    
    return jsonify(tasks[task_id])


@app.route('/api/download/<task_id>/<filename>')
def download_clip(task_id, filename):
    """Télécharge un clip individuel"""
    clip_path = Path('clips_output') / task_id / filename
    
    if not clip_path.exists():
        return jsonify({'error': 'Fichier introuvable'}), 404
    
    return send_file(clip_path, as_attachment=True)


@app.route('/api/download-all/<task_id>')
def download_all(task_id):
    """Télécharge tous les clips en ZIP"""
    output_dir = Path('clips_output') / task_id
    
    if not output_dir.exists():
        return jsonify({'error': 'Dossier introuvable'}), 404
    
    # Créer un ZIP
    zip_path = Path('clips_output') / f'{task_id}.zip'
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for clip in output_dir.glob('clip_*.mp4'):
            zipf.write(clip, clip.name)
    
    return send_file(zip_path, as_attachment=True, download_name='clips.zip')


if __name__ == '__main__':
    # Créer le dossier de sortie
    Path('clips_output').mkdir(exist_ok=True)
    
    # Créer le dossier templates s'il n'existe pas
    Path('templates').mkdir(exist_ok=True)
    
    print("""
    ╔════════════════════════════════════╗
    ║   TikTok Clipper - Web Interface  ║
    ╚════════════════════════════════════╝
    
    🌐 Ouvre ton navigateur sur : http://localhost:5000
    
    """)
    
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
