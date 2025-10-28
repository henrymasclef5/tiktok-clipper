#!/usr/bin/env python3
"""
TikTok Clipper v1.0
Script pour télécharger et découper des vidéos YouTube en clips
"""

import os
import sys
from pathlib import Path
import yt_dlp
from moviepy.editor import VideoFileClip
import math

class TikTokClipper:
    def __init__(self, output_dir="clips_output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
    def download_video(self, youtube_url):
        """Télécharge une vidéo YouTube"""
        print(f"📥 Téléchargement de la vidéo...")
        
        ydl_opts = {
            'format': 'best[height<=1080]',  # Qualité max 1080p
            'outtmpl': 'temp_video.%(ext)s',
            'quiet': False,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
                video_title = info['title']
                filename = ydl.prepare_filename(info)
                print(f"✅ Téléchargement terminé : {video_title}")
                return filename, video_title
        except Exception as e:
            print(f"❌ Erreur lors du téléchargement : {e}")
            return None, None
    
    def cut_video_into_clips(self, video_path, clip_duration=65):
        """Découpe la vidéo en clips de durée spécifiée (en secondes)"""
        print(f"✂️  Découpage de la vidéo en clips de {clip_duration} secondes...")
        
        try:
            video = VideoFileClip(video_path)
            total_duration = video.duration
            num_clips = math.ceil(total_duration / clip_duration)
            
            print(f"📊 Durée totale : {total_duration:.0f}s")
            print(f"📊 Nombre de clips : {num_clips}")
            
            clips_created = []
            
            for i in range(num_clips):
                start_time = i * clip_duration
                end_time = min((i + 1) * clip_duration, total_duration)
                
                # Ignorer les clips trop courts (moins de 30 secondes)
                if end_time - start_time < 30:
                    print(f"⏭️  Clip {i+1} ignoré (trop court)")
                    continue
                
                print(f"⏳ Création du clip {i+1}/{num_clips} ({start_time:.0f}s - {end_time:.0f}s)")
                
                clip = video.subclip(start_time, end_time)
                output_path = self.output_dir / f"clip_{i+1:03d}.mp4"
                
                # Exporter en format TikTok (9:16 vertical)
                # Pour l'instant on garde le format original, on adaptera plus tard
                clip.write_videofile(
                    str(output_path),
                    codec='libx264',
                    audio_codec='aac',
                    fps=30,
                    verbose=False,
                    logger=None
                )
                
                clips_created.append(output_path)
                print(f"✅ Clip {i+1} créé : {output_path}")
            
            video.close()
            return clips_created
            
        except Exception as e:
            print(f"❌ Erreur lors du découpage : {e}")
            return []
    
    def process_video(self, youtube_url, clip_duration=65):
        """Processus complet : téléchargement + découpage"""
        print("🚀 Démarrage du TikTok Clipper")
        print("=" * 50)
        
        # Télécharger
        video_path, title = self.download_video(youtube_url)
        if not video_path:
            return
        
        # Découper
        clips = self.cut_video_into_clips(video_path, clip_duration)
        
        # Nettoyage
        if os.path.exists(video_path):
            os.remove(video_path)
            print("🧹 Fichier temporaire supprimé")
        
        print("=" * 50)
        print(f"✨ Terminé ! {len(clips)} clips créés dans le dossier '{self.output_dir}'")
        
        return clips


def main():
    print("""
    ╔════════════════════════════════════╗
    ║     TikTok Clipper v1.0           ║
    ║  Découpage automatique de vidéos   ║
    ╚════════════════════════════════════╝
    """)
    
    # Demander l'URL
    if len(sys.argv) > 1:
        youtube_url = sys.argv[1]
    else:
        youtube_url = input("🔗 Entre l'URL YouTube : ").strip()
    
    # Demander la durée des clips
    try:
        duration = input("⏱️  Durée de chaque clip en secondes (défaut: 65) : ").strip()
        clip_duration = int(duration) if duration else 65
    except ValueError:
        clip_duration = 65
    
    # Lancer le processus
    clipper = TikTokClipper()
    clipper.process_video(youtube_url, clip_duration)


if __name__ == "__main__":
    main()
