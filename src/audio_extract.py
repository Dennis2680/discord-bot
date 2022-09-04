from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urlparse
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
import datetime
from typing import Dict, Type, Any
from types import TracebackType
import asyncio

from spotify import SpotifyClient


@dataclass
class Song:
    title: str | None
    url: str
    duration: int | None

    def __str__(self) -> str:
        return f'{self.title} ({datetime.timedelta(seconds=self.duration)})\n<{self.url}>'

class YoutubeException(Exception):
    def __init__(self, message: str | None, *args: object) -> None:
        super().__init__(message, *args)

class YoutubeTypeException(YoutubeException):
    def __init__(self, expected_type: Type, actual_type: Type, field_name: str, body: Dict[str, Any], *args: object) -> None:
        self.expected_type: Type = expected_type
        self.actual_type: Type = actual_type
        self.field_name: str = field_name
        self.body = body
        super().__init__(f'Expected \'{field_name}\' to be {expected_type}, got {actual_type} instead\nBody:{body}\n', *args)

class AudioExtractor:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self.__ytdl_args = {
            'format': 'bestaudio/best',
            'audioformat': 'webm',
            'extractaudio': False,
            'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': False,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0',
        }
        self.ytdl = YoutubeDL(self.__ytdl_args)

        self.spotify = SpotifyClient(client_id, client_secret)

    async def __aenter__(self):
        self.spotify = await self.spotify.__aenter__()
        return self

    async def __aexit__(self,
                        exc_type: Type[BaseException] | None,
                        exc_val: BaseException | None,
                        exc_tb: TracebackType | None
                        ) -> None:
        return await self.spotify.__aexit__(exc_type, exc_val, exc_tb)

    async def get_songs(self, song: str, info_only: bool = True):
        try:
            parsed_url = urlparse(song)
            if parsed_url.hostname == 'open.spotify.com':
                self.ytdl.params['extract_flat'] = True
                path = PurePosixPath(parsed_url.path).parts
                if len(path) >= 3 and path[1] == 'playlist':
                    spotify_playlist = [e async for e in self.spotify.get_spotify_playlist(path[2])]
                    for spotify_song in reversed(spotify_playlist):
                        async for ytdl_song in self.get_songs('' if len(spotify_song.artist_names) == 0 else f'{" & ".join(spotify_song.artist_names)} - ' + spotify_song.title):
                            yield ytdl_song
                elif len(path) >= 3 and path[1] == 'track':
                    spotify_song = await self.spotify.get_spotify_song(path[2])
                    async for ytdl_song in self.get_songs('' if len(spotify_song.artist_names) == 0 else f'{" & ".join(spotify_song.artist_names)} - ' + spotify_song.title):
                        yield ytdl_song
            else:
                self.ytdl.params['extract_flat'] = 'in_playlist' if info_only else False


                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(None, lambda: self.ytdl.extract_info(song, download=False))
                if isinstance(info, dict):
                    entries = info.get("entries")
                    if entries is not None and isinstance(entries, list):
                        for entry in info['entries']:
                            if isinstance(entry.get('url'), str):
                                yield Song(entry.get('title'), entry['url'], entry.get('duration'))
                            else:
                                raise YoutubeTypeException(str, type(entry.get('url')), "url") 
                    elif info.get("url") is not None:
                        if isinstance(info.get('url'), str):
                                yield Song(info.get('title'), info['url'], info.get('duration'))
                        else:
                            raise YoutubeTypeException(str, type(entry.get('url')), "url")
                    else:
                        raise YoutubeTypeException()
                else:
                    raise YoutubeTypeException(dict, type(info), "entry info")
        except DownloadError as e:
            raise YoutubeException(e.msg)

    