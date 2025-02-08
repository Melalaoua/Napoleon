import discord
from discord import FFmpegPCMAudio

import json
import asyncio
import random

from yt_dlp import YoutubeDL


def get_video_name(url:str | list[str]) -> str | list[str]:
    """Get video name from Youtube URL

    Args:
        url (str): Youtube video URL

    Returns:
        str: video name
    """
    ydl_opts = {
            'noplaylist':True,
        }
    
    with YoutubeDL(ydl_opts) as ydl:
        if isinstance(url, list):
            video_title = []
            for u in url:
                info_dict = ydl.extract_info(u, download=False)
                video_title.append(info_dict.get('title', None))
            return video_title
        
        info_dict = ydl.extract_info(url, download=False)
        video_title = info_dict.get('title', None)
        return video_title


def download_video(url:str) -> str:
    """Download a video from Youtube

    Args:
        url (str): Youtube video URL
        waitlist (list[str]): List of video URLs coming after the current url

    Returns:
        str: filename path
    """
    ydl_opts = {
            'format': 'mp3/bestaudio/best',
            'outtmpl': f"data/musics/%(title)s.%(ext)s",
            'noplaylist':True,
            # ℹ️ See help(yt_dlp.postprocessor) for a list of available Postprocessors and their arguments
            'postprocessors': [{  # Extract audio using ffmpeg
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }]
        }
    
    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        output_filename = ydl.prepare_filename(info_dict)

    output_filename = output_filename[:-5]+".mp3"
    return output_filename


async def play_sound_discord(filename:str, voice_client:discord.VoiceClient, break_:bool=False) -> None:
    """Play sound in voice channel"""
    try:
        if break_:
            voice_client.stop()
            
        while voice_client.is_playing():
            return False

        voice_client.play(FFmpegPCMAudio(filename))

        while voice_client.is_playing():
            await asyncio.sleep(1)
        
        return True
    except Exception as e :
        print(e)


def get_playlist(default_playlist:bool=True) -> dict:
    with open("data/playlist.json", "r") as f:
        data = json.load(f)
    
    # Get song name from youtube url for default playlist if not done
    for song in data['default_playlist'].keys():
            data['default_playlist'][song] = {"title" : get_video_name(song)} if not data['default_playlist'][song].get("title") else data['default_playlist'][song]

    if default_playlist:
        # Generate default waitlist from default playlist
        keys = list(data['default_playlist'].keys())
        random.shuffle(keys)
        shuffled_playlist = [{'url':key, 'title':data['default_playlist'][key]['title']} for key in keys]
        data['default_waitlist'] = shuffled_playlist
    return data
    


async def play_song(
        bot, 
        voice_state:discord.VoiceClient, 
        default_playlist:bool=False, 
        break_:bool = False, 
        url:str=None, 
        from_position:int=1
    ):
    """Play song in voice channel
    
    Args:
        bot (commands.Bot): bot instance
        voice_state (discord.VoiceClient): Voice client instance
        default_playlist (bool, optional): Use default playlist. Defaults to True.
        break_ (bool, optional): Stop current song. Defaults to False.
        url (str, optional): Youtube URL. Defaults to None.
        from_position (int, optional): Start from position in waitlist. Defaults to 1.
    """
    
    
    while True:
        while True:
            playlist = await asyncio.to_thread(get_playlist, default_playlist=default_playlist)
        
            if playlist['waitlist']:
                waitlist = playlist['waitlist']
            else:
                waitlist = playlist['default_waitlist']
            
            if waitlist:
                break
            else:
                default_playlist=True

        if from_position > len(waitlist):
            from_position = len(waitlist)
        
        with open("data/playlist.json", "w") as f:
                    json.dump(playlist, f, indent=4)

        waitlist = waitlist[from_position-1:]
        
        url = waitlist[0]['url']
        title = waitlist[0]['title']
        waitlist.pop(0)

        if playlist['waitlist']:
            playlist['waitlist'] = waitlist
        else:
            playlist['default_waitlist'] = waitlist
        
        
        filename = await asyncio.to_thread(download_video, url)
        await voice_state.channel.send(f"{random.choice(bot.emojis.music_notes)} Lecture **{title[:100]}**")
        if await play_sound_discord(filename, voice_state, break_=break_):
            if bot.is_paused:
                while bot.is_paused:
                    await asyncio.sleep(1)
            else:
                with open("data/playlist.json", "w") as f:
                    json.dump(playlist, f, indent=4)
        else:
            break
        

def clear_music_folder() -> bool:
    """Clear music folder"""
    import os
    import shutil
    try:
        shutil.rmtree("data/musics")
        os.makedirs("data/musics")
        return True
    except Exception as e:
        print(e)
        return False