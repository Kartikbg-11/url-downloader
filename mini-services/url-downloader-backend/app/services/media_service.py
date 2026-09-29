"""Public media metadata extraction and downloads using yt-dlp."""

import asyncio
from pathlib import Path
from typing import Callable, Optional

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError as YtDlpDownloadError
from imageio_ffmpeg import get_ffmpeg_exe

from app.core.config import get_settings


class MediaService:
    def __init__(self):
        self.settings = get_settings()

    async def get_info(self, url: str) -> dict:
        def extract():
            with YoutubeDL(self._base_options()) as ydl:
                return ydl.extract_info(url, download=False)

        info = await asyncio.to_thread(extract)
        formats = [
            {
                "format_id": f"mp3-{quality}",
                "media_type": "audio",
                "label": f"MP3 {quality} kbps",
                "extension": "mp3",
                "filesize": None,
            }
            for quality in (320, 192, 128)
        ]
        seen = set()

        for item in info.get("formats") or []:
            format_id = str(item.get("format_id") or "")
            extension = item.get("ext") or "bin"
            vcodec = item.get("vcodec")
            acodec = item.get("acodec")
            filesize = item.get("filesize") or item.get("filesize_approx")

            # yt-dlp and FFmpeg will merge video-only formats with best audio.
            if vcodec not in (None, "none"):
                height = item.get("height")
                fps = item.get("fps")
                fps_label = f" {round(fps)}fps" if fps and fps > 30 else ""
                label = f"{height}p{fps_label} {extension.upper()}" if height else f"Video {extension.upper()}"
                key = ("video", label)
                if key not in seen:
                    seen.add(key)
                    formats.append({
                        "format_id": format_id,
                        "media_type": "video",
                        "label": label,
                        "extension": extension,
                        "filesize": filesize,
                    })

            if acodec not in (None, "none") and vcodec in (None, "none"):
                abr = item.get("abr")
                label = f"{round(abr)} kbps {extension.upper()}" if abr else f"Audio {extension.upper()}"
                key = ("audio", label)
                if key not in seen:
                    seen.add(key)
                    formats.append({
                        "format_id": format_id,
                        "media_type": "audio",
                        "label": label,
                        "extension": extension,
                        "filesize": filesize,
                    })

        formats.sort(
            key=lambda value: (
                value["media_type"] != "video",
                -(value.get("filesize") or 0),
            )
        )
        return {
            "title": info.get("title") or "Media",
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "formats": formats,
        }

    async def download(
        self,
        download_id: str,
        url: str,
        format_id: str,
        media_type: str,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> tuple[Path, int]:
        output_template = str(
            self.settings.resolved_download_directory
            / f"{download_id}_%(title).150B.%(ext)s"
        )

        def progress(data: dict):
            if progress_callback:
                progress_callback(data)

        def run_download():
            is_mp3 = format_id.startswith("mp3-")
            selected_format = "bestaudio/best" if is_mp3 else format_id
            if media_type == "video":
                selected_format = f"{format_id}+bestaudio/best"

            options = {
                **self._base_options(),
                "format": selected_format,
                "outtmpl": output_template,
                "windowsfilenames": True,
                "progress_hooks": [progress],
                "ffmpeg_location": get_ffmpeg_exe(),
                # YouTube serves larger formats as segmented streams. A single
                # expired/throttled fragment must not fail the whole download.
                "retries": 10,
                "fragment_retries": 10,
                "file_access_retries": 3,
                "continuedl": True,
                "concurrent_fragment_downloads": 1,
                "socket_timeout": 30,
                "retry_sleep_functions": {
                    "http": lambda attempt: min(2 ** attempt, 20),
                    "fragment": lambda attempt: min(2 ** attempt, 20),
                    "file_access": lambda attempt: min(2 ** attempt, 20),
                },
            }
            if media_type == "video":
                options["merge_output_format"] = "mp4"
            if is_mp3:
                options["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": format_id.removeprefix("mp3-"),
                }]
            with YoutubeDL(options) as ydl:
                try:
                    info = ydl.extract_info(url, download=True)
                except YtDlpDownloadError as exc:
                    # Preserve the actionable extractor message for the UI.
                    message = str(exc).removeprefix("ERROR: ").strip()
                    raise RuntimeError(message or "The media stream could not be downloaded.") from exc
                if is_mp3:
                    expected = Path(ydl.prepare_filename(info)).with_suffix(".mp3")
                    if expected.exists():
                        return expected
                prepared = Path(ydl.prepare_filename(info))
                if prepared.exists():
                    return prepared
                candidates = sorted(
                    self.settings.resolved_download_directory.glob(f"{download_id}_*"),
                    key=lambda item: item.stat().st_mtime,
                    reverse=True,
                )
                if not candidates:
                    raise FileNotFoundError("Downloaded media file was not created.")
                return candidates[0]

        filepath = await asyncio.to_thread(run_download)
        return filepath, filepath.stat().st_size

    @staticmethod
    def _base_options() -> dict:
        """Options shared by inspection and download.

        YouTube's normal web client increasingly requires a per-video Proof of
        Origin token for CDN requests. The mweb client requests that token from
        the installed WPC provider, preventing mid-transfer 403s.
        Keeping this identical for inspection and download also ensures that a
        format offered by the UI is still available when the job starts.
        """
        return {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            # Modern YouTube signatures require an external JS runtime/solver.
            "js_runtimes": {"node": {}},
            "remote_components": {"ejs:github"},
            "extractor_args": {
                "youtube": {
                    "player_client": ["mweb"],
                },
            },
        }


media_service = MediaService()


def get_media_service() -> MediaService:
    return media_service
