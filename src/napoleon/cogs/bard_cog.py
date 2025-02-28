import discord
from discord.ext import commands, tasks

import json
import re

from napoleon import Napoleon
from napoleon_utils.youtube_dl import play_song, clear_music_folder, get_video_name
from emanations.config import get_authorized_channel


class BardDiscord(commands.Cog, ):
    def __init__(self, bot:Napoleon):
        self.bot = bot
        self.db = self.bot.db
        self.http_session = self.bot.http_session
        self.musicfy_key = self.bot.musicfy_key

        self.bard_job.start()
        self.check_members.start()

    def find_youtube_link(self, input_string):
        # Regular expression pattern to match YouTube URLs
        youtube_url_pattern = r'(https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+|https?://youtu\.be/[\w-]+)'

        # Search for the pattern in the input string
        match = re.search(youtube_url_pattern, input_string)

        # If a match is found, return the matched string (YouTube link)
        if match:
            return match.group(0)
        else:
            return None


    def add_to_waitlist(self, ctx:commands.Context, cleaned_message:str):
        with open("data/playlist.json", "r") as f:
            data = json.load(f)
            if not ctx.message.embeds:
                description = get_video_name(cleaned_message)
            else:
                description = ctx.message.embeds[0].title
            
            if len(description) > 100:
                description = description[:100] + "..."
            data['waitlist'].append({"url":cleaned_message, "title": description})
                
        with open("data/playlist.json", "w") as f:
            json.dump(data, f, indent=4)      
        

    async def get_voice_channel(self, guild:discord.Guild):
        authorized_channels = get_authorized_channel(guild.id, "napoléon")
        if authorized_channels:
            channel = self.bot.get_channel(authorized_channels[0])
            if channel.type == discord.ChannelType.voice:
                return channel

    
    @tasks.loop(seconds=5)
    async def bard_job(self):
        for guild in self.bot.guilds:
            channel = await self.get_voice_channel(guild)
            
            if channel:
                voice_state = guild.voice_client
                if voice_state and voice_state.channel:
                    if voice_state.channel.id != channel.id:
                        await voice_state.move_to(channel)
                        await play_song(self.bot, voice_state)
                    else:
                        return
                else:
                    voice_state = await channel.connect()
                    await play_song(self.bot, voice_state)


    @tasks.loop(seconds=10)
    async def check_members(self):
        for guild in self.bot.guilds:
            channel = await self.get_voice_channel(guild)

            if channel:
                voice_state = guild.voice_client
                if voice_state and voice_state.channel:
                    if voice_state.channel.id == channel.id:
                        if len(voice_state.channel.members) <= 1:
                            self.bot.is_paused=True
                            voice_state.pause()
                    else:
                        return
    

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        channel = await self.get_voice_channel(member.guild)
        
        if before.channel is None and after.channel:
            if after.channel.id == channel.id:
                self.bot.is_paused=False
                

    @bard_job.before_loop
    async def before_bard_job(self):
        clear_music_folder()
        await self.bot.wait_until_ready()

    @commands.command(
        name="play",
        description="Ajoute une musique à la playlist",
    )
    async def play(self, ctx:commands.Context) -> None:
        channel = await self.get_voice_channel(ctx.guild)
        cleaned_message = self.find_youtube_link(ctx.message.content)

        if ctx.channel.id != channel.id :
            return
        
        if self.bot.is_paused:
            self.bot.is_paused = False
            await ctx.message.add_reaction("👍")
            return
        
        if cleaned_message:
            self.add_to_waitlist(ctx, cleaned_message)
            await ctx.message.add_reaction("👍")        
        else:
            voice_client = ctx.guild.voice_client
            if not voice_client.is_playing():
                await play_song(self.bot, voice_client, default_playlist=False)

            

    @commands.command(
        name="next",
        description="Joue la prochaine musique dans la playlist"
    )
    async def next(self, ctx:commands.Context, number:int = 1) -> None:
        
        channel = await self.get_voice_channel(ctx.guild)
        if not channel: 
            return
        
        if ctx.channel.id != channel.id:
            return
        
        voice_state :discord.VoiceClient = ctx.guild.voice_client
        if voice_state and voice_state.channel:
            if voice_state.channel.id != channel.id:
                await voice_state.move_to(channel)
        else:
            voice_state = await channel.connect()
        await ctx.message.add_reaction("👍")        
        await play_song(self.bot, voice_state, default_playlist=False, break_=True, from_position=number)
        
        
            
        
    @commands.command(
        name="queue",
        description="Ajoute une musique dans la playlist"
    )
    async def queue(self, ctx:commands.Context) -> None:
        channel = await self.get_voice_channel(ctx.guild)
        if ctx.channel.id != channel.id:
            return
        return await self.gen_queue_embed(ctx)
        

    async def gen_queue_embed(self, ctx):
        with open("data/playlist.json", "r") as f:
            data = json.load(f)
        
        user_waitlist = data['waitlist']
        default_waitlist = data['default_waitlist']

        waitlist = user_waitlist + default_waitlist
        
        if waitlist:
            embed = discord.Embed(
                title="Playlist",
                description=f"\n".join([f"- **{song['title']}**" for song in waitlist[:10]]),
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"La playlist est vide (la playlist par défaut est actuellement jouée par {self.bot.user.mention})")
        

    @commands.command(
        name="pause",
        description="Met en pause la musique en cours"
    )
    async def pause(self, ctx:commands.Context) -> None:
        voice_state = ctx.guild.voice_client
        self.bot.is_paused = True
        if voice_state and voice_state.is_playing():
            voice_state.pause()
            await ctx.message.add_reaction("👍") 

    
    @commands.command(
        name="clear",
        description="Vide la playlist"
    )
    async def clear_queue(self, ctx:commands.Context) -> None:
        with open("data/playlist.json", "r") as f:
            data = json.load(f)
            data['waitlist'] = []
            data['default_waitlist'] = []
        
        with open("data/playlist.json", "w") as f:
            json.dump(data, f, indent=4)
        await ctx.message.add_reaction("👍")


async def setup(bot:commands.Bot):
    await bot.add_cog(BardDiscord(bot))


    