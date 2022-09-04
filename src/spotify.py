from types import TracebackType
from typing import Optional, Type, List
from aiohttp import ClientSession
from datetime import datetime, timedelta
from dataclasses import dataclass

SPOTIFY_CLIENT_ID = "d772bb5aed704bcbab78f28492a301f5"
SPOTIFY_CLIENT_SECRET = "8860e96d0ff243c198123b622637497e"

@dataclass
class SpotifyTrack:
    title: str
    artist_names: List[str]

    def __str__(self) -> str:
        return f'{self.title} - {self.artist_name}'


class SpotifyException(Exception):
    def __init__(self, status_code: int, body: bytes, message: Optional[str], *args: object) -> None:
        self.status_code: int = status_code
        self.body: bytes = body

        super().__init__(
            f'{self.status_code}\n{body}' if message is None else message, *args)


class SpotifyTypeException(SpotifyException):
    def __init__(self, expected_type: Type, actual_type: Type, field_name: str, status_code: int, body: bytes, *args: object) -> None:
        self.expected_type: Type = expected_type
        self.actual_type: Type = actual_type
        self.field_name: str = field_name
        super().__init__(status_code, body,
                         f'Expected \'{field_name}\' to be {expected_type}, got {actual_type} instead\nHTTP {self.status_code}\n{body}\n', *args)


class SpotifyClient:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self.http_session: ClientSession = ClientSession()

        self.access_token: Optional[str] = None
        self.expires_time: datetime = datetime.utcnow()

        self.client_id: str = client_id
        self.client_secret = client_secret

    async def __aenter__(self):
        self.http_session = await self.http_session.__aenter__()
        return self

    async def __aexit__(self,
                        exc_type: Optional[Type[BaseException]],
                        exc_val: Optional[BaseException],
                        exc_tb: Optional[TracebackType]
                        ) -> None:
        return await self.http_session.__aexit__(exc_type, exc_val, exc_tb)

    async def authenticate(self):
        url = "https://accounts.spotify.com/api/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }

        async with self.http_session.post(url, data=payload, headers=headers) as response:
            if response.status == 200:
                parsed = await response.json()
                if isinstance(parsed, dict):
                    if isinstance(parsed.get('access_token'), str):
                        self.access_token = parsed['access_token']
                    else:
                        raise SpotifyTypeException(str, type(parsed.get('access_token')), 'access_token', response.status, await response.content.read())

                    if isinstance(parsed.get('expires_in'), int):
                        self.expires_time = datetime.utcnow(
                        ) + timedelta(seconds=parsed['expires_in'])
                    else:
                        raise SpotifyTypeException(int, type(parsed.get('expires_in')), 'expires_in', response.status, await response.content.read())
                else:
                    raise SpotifyTypeException(dict, type(parsed), '<body>', response.status, await response.content.read())
            else:
                raise SpotifyException(response.status, await response.content.read())

    async def get_spotify_playlist(self, playlist_id: str):
        if self.expires_time >= datetime.utcnow() or self.access_token is None:
            self.authenticate()
        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}"
        }
        params = {
            "playlist_id": playlist_id,
            "fields": "items(track(id,name,artists(name)))"
        }
        async with self.http_session.get(url, params=params, headers=headers) as response:
            if response.status == 200:
                parsed = await response.json()
                if isinstance(parsed, dict):
                    if isinstance(parsed.get('items'), dict):
                        for item in parsed['items']:
                            if isinstance(item.get('track'), dict):
                                if isinstance(item['track'].get('name'), str):
                                    if isinstance(item['track'].get('artists'), list) and all(map(lambda e: isinstance(e, dict) and isinstance(e.get('name'), str), item['track']['artists'])):
                                        yield SpotifyTrack(item['track']['name'], list(map(lambda e: e['name'], item['track']['artists'])))
                                    else:
                                        raise SpotifyTypeException(List[str], type(parsed['items']['track'].get('artists')), 'artists', response.status, await response.content.read())
                                else:
                                    raise SpotifyTypeException(str, type(parsed['items']['track'].get('name')), 'song name', response.status, await response.content.read())
                        else:
                            raise SpotifyTypeException(dict, type(parsed['items'].get('track')), 'track', response.status, await response.content.read())
                    else:
                        raise SpotifyTypeException(dict, type(parsed.get('items')), 'items', response.status, await response.content.read())
                else:
                    raise SpotifyTypeException(dict, type(parsed), '<body>', response.status, await response.content.read())
            else:
                raise SpotifyException(response.status, await response.content.read())

    async def get_spotify_song(self, song_id: str):
        if self.expires_time >= datetime.utcnow() or self.access_token is None:
            self.authenticate()
        url = f"https://api.spotify.com/v1/tracks/{song_id}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}"
        }
        async with self.http_session.get(url, headers=headers) as response:
            if response.status == 200:
                parsed = await response.json()
                if isinstance(parsed, dict):
                    if isinstance(parsed.get('name'), str):
                        if isinstance(parsed.get('artists'), list) and all(map(lambda e: isinstance(e, dict) and isinstance(e.get('name'), str), parsed['artists'])):
                            return SpotifyTrack(parsed['name'], list(map(lambda e: e['name'], parsed['artists'])))
                        else:
                            raise SpotifyTypeException(List[str], type(parsed.get('artists')), 'artists', response.status, await response.content.read())
                    else:
                        raise SpotifyTypeException(str, type(parsed.get('name')), 'song name', response.status, await response.content.read())
                else:
                    raise SpotifyTypeException(dict, type(parsed), '<body>', response.status, await response.content.read())
            else:
                raise SpotifyException(response.status, await response.content.read())
