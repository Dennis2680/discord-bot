from nextcord import Interaction, Member, VoiceState, Intents, FFmpegOpusAudio
from nextcord.ext import commands
from random import random
from collections import deque, defaultdict
from audio_extract import Song, AudioExtractor
import os

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

intents = Intents.default()
intents.members = True
intents.voice_states = True

client = commands.Bot(intents=intents)


queues: defaultdict[int, deque[Song]] = defaultdict(deque)

async def play_song(interaction: Interaction, audio_ext: AudioExtractor):
    q = queues[interaction.guild.id]
    song = q.pop() if q else None
    if song:
        info: Song = await anext(audio_ext.get_songs(song.url, False))
        interaction.guild.voice_client.play(FFmpegOpusAudio(info.url, **FFMPEG_OPTIONS),
                after=lambda _: play_song(interaction, audio_ext))


@client.slash_command(name="shuffle", description="shuffles current song queue")
async def shuffle(interaction: Interaction):
    random.shuffle(queues[interaction.guild.id])
    await interaction.response.send_message("Songs have been shuffled")

@client.slash_command(name="join", description="makes the bot join the voice chat")
async def join(interaction: Interaction):
    if interaction.user.voice is not None:
        await interaction.user.voice.channel.connect()
        await interaction.response.send_message("bot has joined")
    else:
        await interaction.response.send_message("you are not in a voice chat")

@client.slash_command(name="leave", description="makes the bot leave the voice chat")
async def leave(interaction: Interaction):
    if interaction.guild.voice_client is not None:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("bot has left")
    else:
        await interaction.response.send_message("bot is not in a voice chat")

@client.slash_command(name="pause")
async def pause(interaction: Interaction):
    if interaction.guild.voice_client is not None and interaction.guild.voice_client.is_connected():
        if hasattr(interaction.guild.voice_client, 'is_paused') and interaction.guild.voice_client.is_paused():
            return await interaction.response.send_message("Music already paused");
        try:
            interaction.guild.voice_client.pause()
            await interaction.response.send_message("Music has been paused")
        except Exception as e:
            await interaction.response.send_message(str(e))
    else:
        await interaction.response.send_message("No song is playing")

@client.slash_command(name="play")
async def play(interaction: Interaction, song_url: str | None = None):
    await interaction.response.defer()
    if interaction.user.voice is None:
        return await interaction.followup.send('You\'re not in the channel')
    
    if interaction.guild.voice_client is None or not interaction.guild.voice_client.is_connected():
        await interaction.user.voice.channel.connect()
    
    async with AudioExtractor(os.environ['SPOTIFY_CLIENT_ID'], os.environ['SPOTIFY_CLIENT_SECRET']) as audio_ext:    
        if song_url is not None:
            async for song in audio_ext.get_songs(song_url):
                queues[interaction.guild_id].append(song)
        else:
            if not queues[interaction.guild.id]:
                return await interaction.followup.send("No songs queued")
        if interaction.guild.voice_client.is_playing():
            return await interaction.followup.send("Music already playing")
        elif hasattr(interaction.guild.voice_client, 'is_paused') and interaction.guild.voice_client.is_paused():
            interaction.guild.voice_client.resume()
            return await interaction.followup.send("Music has been resumed")
        else:
            await play_song(interaction, audio_ext)
            return await interaction.followup.send("Music played")

@client.slash_command(name="skip")
async def skip(interaction: Interaction):
    if interaction.guild.voice_client is not None and (interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused()):
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("Song skipped")
    else:
        await interaction.response.send_message("No songs playing")

@client.slash_command(name="stop")
async def stop(interaction: Interaction):
    await interaction.response.defer()
    queues[interaction.guild.id].clear()

    if interaction.guild.voice_client is not None:
        interaction.guild.voice_client.stop()
        await interaction.guild.voice_client.disconnect()

    await interaction.followup.send("Music stopped")

@client.event
async def on_voice_state_update(member: Member, before: VoiceState, after: VoiceState):
    if member.id is client.user.id:
        return

    if member.guild.voice_client is not None and len(member.guild.voice_client.channel.members) == 1:
        await member.guild.voice_client.disconnect()

@client.event
async def on_ready():
    print("bot is online")

client.run(os.environ['DISCORD_KEY'])