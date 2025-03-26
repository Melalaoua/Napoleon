import discord
from discord import FFmpegPCMAudio

import traceback

import json
import asyncio
import random
import os
import shutil
from yt_dlp import YoutubeDL

class MusicPlayer:
    def __init__(self, bot):
        self.bot = bot
        self.is_paused = False
        self.current_song = None
        self._setup_directories()

    def _setup_directories(self):
        """Assure que le répertoire de musique existe"""
        os.makedirs("data/musics", exist_ok=True)

    def get_video_info(self, url):
        """Récupère les informations d'une vidéo YouTube"""
        ydl_opts = {'noplaylist': True}

        with YoutubeDL(ydl_opts) as ydl:
            if isinstance(url, list):
                return [ydl.extract_info(u, download=False).get('title', None) for u in url]
            return ydl.extract_info(url, download=False).get('title', None)

    def download_video(self, url: str) -> str:
        """Télécharge une vidéo depuis Youtube"""
        ydl_opts = {
            'format': 'mp3/bestaudio/best',
            'outtmpl': f"data/musics/%(id)s.%(ext)s",  # Utiliser l'ID plutôt que le titre
            'noplaylist': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }]
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            title = info_dict.get('title')
            video_id = info_dict.get('id')
            
            # Vérifier si le fichier existe déjà
            output_filename = f"data/musics/{video_id}.mp3"
            if os.path.exists(output_filename):
                return output_filename, title
                
            # Sinon, télécharger
            info_dict = ydl.extract_info(url, download=True)
        
        return output_filename, title

    async def play_sound(self, filename, voice_client, interrupt=False):
        """Joue un fichier audio dans un canal vocal"""
        if not voice_client:
            return False
        if interrupt and voice_client.is_playing():
            voice_client.stop()

        if voice_client.is_playing():
            return False

        voice_client.play(FFmpegPCMAudio(filename))

        while voice_client.is_playing() or self.is_paused:
            await asyncio.sleep(0.5)

        return True

    def load_playlist(self):
        """Charge la playlist depuis le fichier"""
        try:
            with open("data/playlist.json", "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Fichier inexistant ou corrompu
            default = {"default_playlist": {}, "default_waitlist": [], "waitlist": []}
            with open("data/playlist.json", "w") as f:
                json.dump(default, f, indent=4)
            return default

    def save_playlist(self, playlist):
        """Sauvegarde la playlist dans le fichier"""
        with open("data/playlist.json", "w") as f:
            json.dump(playlist, f, indent=4)

    def update_default_playlist(self, playlist):
        """Met à jour les titres dans la playlist par défaut"""
        modified = False
        for song in playlist['default_playlist'].keys():
            if not playlist['default_playlist'][song].get("title"):
                playlist['default_playlist'][song] = {"title": self.get_video_info(song)}
                modified = True
        return playlist, modified

    async def play_queue(self, voice_client, channel, default_playlist=False, interrupt=False, from_position=1):
        """Joue la file d'attente de musique"""
        while True:
            # Charge la playlist
            playlist = self.load_playlist()
            playlist, modified = self.update_default_playlist(playlist)
            if modified:
                self.save_playlist(playlist)

            #Détermine quelle liste utiliser
            if playlist['waitlist']:
                waitlist = playlist['waitlist']
            elif not playlist['default_waitlist'] and playlist['default_playlist']:
                # Génère une nouvelle liste par défaut si nécessaire
                keys = list(playlist['default_playlist'].keys())
                random.shuffle(keys)
                waitlist = [{'url': key, 'title': playlist['default_playlist'][key]['title']} 
                           for key in keys]
                playlist['default_waitlist'] = waitlist
                self.save_playlist(playlist)
            else:
                waitlist = playlist['default_waitlist']

            if not waitlist:
                await asyncio.sleep(1)
                continue

            #Ajuste la position de départ
            if from_position > len(waitlist):
                from_position = 1

            waitlist = waitlist[from_position-1:]

            #Obtient la prochaine chanson
            song = waitlist[0]
            waitlist.pop(0)

            #Met à jour la playlist
            if playlist['waitlist'] and waitlist is playlist['waitlist']:
                playlist['waitlist'] = waitlist
            else:
                playlist['default_waitlist'] = waitlist
            self.save_playlist(playlist)

            #Télécharge et joue la chanson
            try:
                filename,title = self.download_video(song['url'])
                self.current_song = title

                await channel.send(f"{random.choice(['🎵', '🎶', '🎸', '🎷', '🎺', '🥁'])} Lecture {title[:100]}")

                if await self.play_sound(filename, voice_client, interrupt):
                    if not voice_client.is_connected():
                        break

                    self.current_song = None
                else:
                    break
            except Exception as e:
                traceback.print_exc()
                await channel.send(f"Erreur lors de la lecture: {str(e)[:100]}")
                await asyncio.sleep(1)

    def clear_music_folder(self):
        """Nettoie le dossier de musique"""
        try:
            shutil.rmtree("data/musics")
            os.makedirs("data/musics", exist_ok=True)
            return True
        except Exception:
            return False