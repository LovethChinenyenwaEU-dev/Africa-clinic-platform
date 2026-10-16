"""The one door to video providers (FR-C3, FR-I3).

The consult room asks a VideoProvider for a room; the screens only ever see links.
Swapping Jitsi for a paid provider (Daily, Twilio, JaaS) means one new class here.

Rules:
- A room name is long and random, so it cannot be guessed. No patient name, clinic
  name or ID ever goes into a room name or link.
- Audio-only is the same room with video switched off, so switching from video to
  audio (FR-C4) never needs a new call.
"""
import secrets
from dataclasses import dataclass
from typing import Protocol

from app.core.config import settings


@dataclass(frozen=True)
class RoomLinks:
    video_url: str | None  # None: this provider offers no video (text only)
    audio_url: str | None


class VideoProvider(Protocol):
    name: str

    def new_room_name(self) -> str: ...

    def links(self, room_name: str) -> RoomLinks: ...


class JitsiProvider:
    """Jitsi Meet: free, runs in the browser, no account. Options go after "#"."""

    name = "jitsi"

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def new_room_name(self) -> str:
        return f"clinic-{secrets.token_urlsafe(18)}"

    def links(self, room_name: str) -> RoomLinks:
        room = f"{self.base_url}/{room_name}"
        # Low-bandwidth defaults: lower resolution for video, camera off for audio.
        video = f"{room}#config.resolution=360&config.prejoinConfig.enabled=true"
        audio = f"{room}#config.startAudioOnly=true&config.startWithVideoMuted=true"
        return RoomLinks(video_url=video, audio_url=audio)


class FakeVideoProvider:
    """For tests: predictable links, nothing leaves the machine."""

    name = "fake"

    def new_room_name(self) -> str:
        return f"fake-{secrets.token_hex(8)}"

    def links(self, room_name: str) -> RoomLinks:
        return RoomLinks(
            video_url=f"https://video.invalid/{room_name}",
            audio_url=f"https://video.invalid/{room_name}?audio",
        )


class NoVideoProvider:
    """Video switched off: consults run on chat (text)."""

    name = "none"

    def new_room_name(self) -> str:
        return f"none-{secrets.token_hex(8)}"

    def links(self, room_name: str) -> RoomLinks:
        return RoomLinks(video_url=None, audio_url=None)


def provider_named(name: str) -> VideoProvider:
    if name == "jitsi":
        return JitsiProvider(settings.jitsi_base_url)
    if name == "fake":
        return FakeVideoProvider()
    return NoVideoProvider()


def get_video_provider() -> VideoProvider:
    """The provider this server is set up for (VIDEO_PROVIDER)."""
    return provider_named(settings.video_provider)
