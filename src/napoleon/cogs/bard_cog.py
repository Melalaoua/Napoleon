import discord
from discord.ext import commands, tasks
import re

from emanations.config import get_authorized_channel
from napoleon_utils.youtube_dl import MusicPlayer

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.player = self.bot.music_player
        self.voice_clients = {}

        #Démarrage des tâches périodiques
        self.music_loop.start()
        self.check_idle.start()

    def extract_youtube_url(self, text):
        """Extrait une URL YouTube d'un texte"""
        pattern = r'(https?://(?:www.)?(?:youtube.com/watch?v=|youtu.be/)[\w-]+)'
        match = re.search(pattern, text)
        return match.group(0) if match else None

    def add_to_waitlist(self, url, title=None):
        """Ajoute une URL à la file d'attente"""
        playlist = self.player.load_playlist()

        if not title:
            title = self.player.get_video_info(url)

        if len(title) > 100:
            title = title[:97] + "..."

        playlist['waitlist'].append({"url": url, "title": title})
        self.player.save_playlist(playlist)

    async def get_voice_channel(self, guild:discord.Guild):
        authorized_channels = get_authorized_channel(guild.id, "napoléon")
        if authorized_channels:
            channel = self.bot.get_channel(authorized_channels[0])
            if channel.type == discord.ChannelType.voice:
                return channel

    @tasks.loop(seconds=5)
    async def music_loop(self):
        """Boucle principale pour gérer la musique"""
        for guild in self.bot.guilds:
            channel = await self.get_voice_channel(guild)
            if not channel:
                continue

            voice_client = guild.voice_client

            #Connexion ou déplacement vers le canal approprié
            if voice_client:
                if voice_client.channel.id != channel.id:
                    await voice_client.move_to(channel)
                    self.voice_clients[guild.id] = voice_client
                    await self.player.play_queue(voice_client, channel)
            else:
                try:
                    voice_client = await channel.connect()
                    self.voice_clients[guild.id] = voice_client
                    await self.player.play_queue(voice_client, channel)
                except Exception:
                    continue

    @tasks.loop(seconds=10)
    async def check_idle(self):
        """Vérifie si le bot est seul dans un canal vocal"""
        for guild in self.bot.guilds:
            voice_client = guild.voice_client
            if not voice_client or not voice_client.is_connected():
                continue

            if len(voice_client.channel.members) <= 1:
                # Seul le bot est présent
                if voice_client.is_playing() and not self.player.is_paused:
                    self.player.is_paused = True
                    voice_client.pause()
            elif self.player.is_paused:
                # Des membres sont présents, reprendre si en pause
                self.player.is_paused = False
                if voice_client.is_paused():
                     voice_client.resume()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Réagit aux changements d'état vocal des membres"""
        if member.bot:
            return

        guild = member.guild
        voice_client = guild.voice_client

        if not voice_client:
            return

        #Quelqu'un rejoint le canal du bot
        if after and after.channel and after.channel.id == voice_client.channel.id:
            if self.player.is_paused:
                self.player.is_paused = False
                voice_client.resume()

    @music_loop.before_loop
    async def before_music_loop(self):
        """Initialisation avant le démarrage de la boucle"""
        # self.player.clear_music_folder()
        await self.bot.wait_until_ready()

    @commands.command(name="play")
    async def play_command(self, ctx):
        """Commande pour ajouter une musique à la playlist"""
        channel = await self.get_voice_channel(ctx.guild)
        if not channel or ctx.channel.id != channel.id:
            return

        if self.player.is_paused:
            self.player.is_paused = False
            if ctx.guild.voice_client and ctx.guild.voice_client.is_paused():
                ctx.guild.voice_client.resume()
            await ctx.message.add_reaction("👍")
            return

        url = self.extract_youtube_url(ctx.message.content)
        if url:
            self.add_to_waitlist(url)
            await ctx.message.add_reaction("👍")
        elif ctx.guild.voice_client and not ctx.guild.voice_client.is_playing():
            await self.player.play_queue(ctx.guild.voice_client, channel)

    @commands.command(name="next")
    async def next_command(self, ctx, number: int = 1):
        """Passe à la musique suivante"""
        channel = await self.get_voice_channel(ctx.guild)
        if not channel or ctx.channel.id != channel.id:
            return

        voice_client = ctx.guild.voice_client
        if not voice_client:
            voice_client = await channel.connect()
        elif voice_client.channel.id != channel.id:
            await voice_client.move_to(channel)

        await ctx.message.add_reaction("👍")
        await self.player.play_queue(voice_client, channel, interrupt=True, from_position=number)

    @commands.command(name="queue")
    async def queue_command(self, ctx):
        """Affiche la file d'attente"""
        channel = await self.get_voice_channel(ctx.guild)
        if not channel or ctx.channel.id != channel.id:
            return

        playlist = self.player.load_playlist()
        user_waitlist = playlist['waitlist']
        default_waitlist = playlist['default_waitlist']

        combined = user_waitlist + default_waitlist

        if combined:
            embed = discord.Embed(
                title="Playlist",
                description="\n".join([f"{i+1}. {song['title']}" for i, song in enumerate(combined[:10])]),
                color=discord.Color.blue()
            )
            if self.player.current_song:
                embed.set_footer(text=f"En cours: {self.player.current_song}")
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"La playlist est vide (la playlist par défaut est actuellement jouée par {self.bot.user.mention})")

    @commands.command(name="pause")
    async def pause_command(self, ctx):
        """Met en pause la musique"""
        voice_client = ctx.guild.voice_client
        if voice_client and voice_client.is_playing():
            self.player.is_paused = True
            voice_client.pause()
            await ctx.message.add_reaction("👍")

    @commands.command(name="clear")
    async def clearcommand(self, ctx):
        """Vide la file d'attente"""
        playlist = self.player.load_playlist()
        playlist['waitlist'] = []
        playlist['default_waitlist'] = []
        self.player.save_playlist(playlist)
        await ctx.message.add_reaction("👍")

async def setup(bot):
    # Initialiser le lecteur de musique
    if not hasattr(bot, 'music_player'):
        bot.music_player = MusicPlayer(bot)
    await bot.add_cog(MusicCog(bot))