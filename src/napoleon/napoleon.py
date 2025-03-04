import os
from dotenv import load_dotenv
load_dotenv()

import discord
from discord.ext import commands

import aiohttp

import asyncio
import logging
import logging.handlers

logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)

handler = logging.handlers.RotatingFileHandler(
filename='napoleon-discord.log',
encoding='utf-8',
maxBytes=32 * 1024 * 1024,  # 32 MiB
backupCount=5,  # Rotate through 5 files
)
dt_fmt = '%Y-%m-%d %H:%M:%S'
formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
handler.setFormatter(formatter)
logger.addHandler(handler)


from emanations import DiscordBot

from emanations.database import AsyncDb
from emanations.api.llm import OpenAIServerModel, AngelariumAgent
from emanations.api.diffusion.stability import StabilityAI
from emanations.api.tts.elevenlabs import ElevenLabs

from napoleon_utils.config import Emojis, Prompts



class Napoleon(DiscordBot):
    def __init__(
        self, 
        *args,
        **kwargs
    ) -> commands.Bot:
        """Initialize Bard bot"""
        super().__init__(*args, **kwargs)
        self.musicfy_key = kwargs.get("musicfy_key")
        self.http_session = kwargs.get("http_session")
        self.is_paused=False

    @property
    def emojis(self):
        return Emojis
    
    @property
    def bot_description(self):
        return "Napol-On est un musicien d'une grande distinction, chargé de l'honneur de jouer de la musique classique avec une régularité et une assiduité qui ne connaissent point de relâche."

    
async def main():
    db = AsyncDb(os.getenv("DB_URI"))
    llm = OpenAIServerModel(
        model_id="llama-3.3-70b-versatile", api_base="https://api.groq.com/openai/v1", api_key=os.getenv("GROQ_KEY")
    )
    
    agent = AngelariumAgent(
        llm=llm,
        prompts=Prompts,
        db=db,
    )
    stability = StabilityAI(os.getenv("STABILITY_KEY"))
    elevenlabs = ElevenLabs(os.getenv("ELEVENLABS_KEY"))

    await db.begin()
    async with aiohttp.ClientSession() as http_session:
        async with Napoleon(
            name="Napoléon",
            db = db,
            cogs_path="cogs",
            llm = llm,
            agent=agent,
            stability = stability,
            elevenlabs = elevenlabs,
            http_session = http_session,
            musicfy_key = os.getenv("MUSICFY_KEY"),

            intents=discord.Intents.all(),
            command_prefix= list(os.getenv('PREFIXES')),
            strip_after_prefix = True,
            help_command=None,
        ) as bot:
            try:
                await bot.start(os.getenv("DISCORD_TOKEN"))
            except KeyboardInterrupt:
                await bot.close()

if __name__ == '__main__':
    asyncio.run(main())