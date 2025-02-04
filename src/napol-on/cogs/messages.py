import discord
from discord.ext import commands

from sqlalchemy.ext.asyncio import AsyncSession

from emanations.database.crud import CrudFactory
from emanations.database.models.discordmodels import (
    DiscordPrivateMessage, DiscordPrivateMessageSchema
)

from napol import Napol
from emanations.observers import Observer, Observable, CogObservableMetaclass
from emanations.angelarium import ExperienceObserver

class MessageDiscord(commands.Cog, Observable, metaclass=CogObservableMetaclass):
    def __init__(self, bot:Napol):
        self.bot = bot
        self.db = self.bot.db
        self.llm = self.bot.llm
        self.stability = self.bot.stability
        self.elevenlabs = self.bot.elevenlabs
        
        self.action_ = "message"
        self.observers_ : list[Observer] = []
        self.add_observer(ExperienceObserver())
    
    def add_observer(self, *args):
        for observer in args:
            self.observers_.append(observer)
    
    def remove_observer(self, observer):
        self.observers_.remove(observer)
    
    async def notify_observers(self):
        for observer in self.observers_: await observer.update(self)


    @commands.Cog.listener()
    async def on_message(
        self, 
        message:discord.Message
    ) -> None:
        """When a message is sent in the discord, load message in database"""
        if isinstance(message.channel, (discord.DMChannel, discord.GroupChannel)):
            message_create = DiscordPrivateMessageSchema(
                uuid = message.id,
                author_uuid = message.author.id,
                created_at = message.created_at.replace(tzinfo=None),
                content = message.content,
                metadatas = await message_metadata(message)
            )
            return await load_privates_messages(self.db, message_create)

        
async def setup(bot:Napol) -> None:
    await bot.add_cog(MessageDiscord(bot))
    

async def load_privates_messages(
        session:AsyncSession,
        messages_create : list[DiscordPrivateMessageSchema]
) -> None:
    """Builk create private message in database
    
    Args:
        message (list[DiscordPrivateMessageSchema]): List of private messages schema from emanations package 

    Returns:
        None
    """
    PrivateMessageCrud = CrudFactory(DiscordPrivateMessage)
    message = await PrivateMessageCrud.create(session, messages_create)
    if not message:
        raise Exception("Error while creating private message") 


async def message_metadata(
        message:discord.Message
) -> dict:
    """Return additional information to str like activity, interaction, stickers.
    
    Args:
        message (discord.Message): Discord message
    
    Returns:
        str: Additional information
    """
    metadata = {}
    if getattr(message, 'attachments', None):
        metadata["attachments"] = []
        for attachment in message.attachments:
            attachment : discord.Attachment = attachment
            attachment_dict = {}
            attachment_dict["filename"] = attachment.filename
            attachment_dict['url'] = attachment.url
            attachment_dict['proxy_url'] = attachment.proxy_url
            attachment_dict['size'] = attachment.size
            attachment_dict['ephemeral'] = attachment.ephemeral
            attachment_dict["voice_message"] = attachment.is_voice_message()
            attachment_dict['duration'] = attachment.duration
            attachment_dict['waveform'] = attachment.waveform
            attachment_dict['spoiler'] = attachment.is_spoiler()
            metadata["attachments"].append(attachment_dict)

    metadata["channel_mentions"] = [channel.name for channel in message.channel_mentions]    
    metadata["mention_everyone"] = message.mention_everyone
    metadata["roles_mentions"] = [role.name for role in message.role_mentions]
    metadata["flags"] = {k : v for k,v in iter(message.flags)}
    
    if getattr(message, "interaction_metadata"):
        metadata["interaction_metadata"] = {
            "type" : message.interaction_metadata.type,
            "original_response_message_id" : message.interaction_metadata.original_response_message_id,
            "interacted_message_id" : message.interaction_metadata.interacted_message_id,

        }
    
    metadata["stickers"] = [sticker.name for sticker in message.stickers]
    
    metadata["embeds"] = []
    for embed in message.embeds:
        metadata["embeds"].append(embed.to_dict())    
    return metadata

