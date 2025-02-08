import asyncio
import json
import aiohttp

import pyytlounge
from aiohttp import ClientSession

from .constants import youtube_client_blacklist

create_task = asyncio.create_task


class YtLoungeApi(pyytlounge.YtLoungeApi):
    def __init__(
        self,
        screen_id,
        config=None,
        api_helper=None,
        logger=None,
        web_session: ClientSession = None,
    ):
        super().__init__("SkipAdsTV", logger=logger)

        self.logger = logger
        self.auth.screen_id = screen_id
        self.auth.lounge_id_token = None
        self.api_helper = api_helper
        self.volume_state = {}
        self.subscribe_task = None
        self.subscribe_task_watchdog = None
        self.callback = None
        self.shorts_disconnected = False
        self.auto_play = config.auto_play if config else True
        self.mute_ads = True
        self.skip_ads = True

        # Dùng session được truyền vào hoặc tạo mới
        if web_session:
            self.session = web_session
        else:
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": self.modify_user_agent(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )}
            )

    def modify_user_agent(self, user_agent: str) -> str:
        """Chỉnh sửa User-Agent để phù hợp với YouTube."""
        if "youtube.com" in user_agent.lower():
            return user_agent.replace(")", "; Mediapartners-Google)")
        return user_agent

    async def fetch(self, url, **kwargs):
        """Hàm gửi request với User-Agent được chỉnh sửa."""
        headers = kwargs.pop("headers", {})
        headers["User-Agent"] = self.modify_user_agent(headers.get("User-Agent", ""))
        async with self.session.get(url, headers=headers, **kwargs) as response:
            return await response.text()

    async def _watchdog(self):
        """Đảm bảo vẫn kết nối đến lounge."""
        await asyncio.sleep(35)
        try:
            self.subscribe_task.cancel()
        except Exception:
            pass

    async def subscribe_monitored(self, callback):
        """Đăng ký vào lounge với giám sát."""
        self.callback = callback
        try:
            self.subscribe_task_watchdog.cancel()
        except:
            pass
        self.subscribe_task = asyncio.create_task(super().subscribe(callback))
        self.subscribe_task_watchdog = asyncio.create_task(self._watchdog())
        return self.subscribe_task

    def _process_event(self, event_id: int, event_type: str, args):
        """Xử lý sự kiện nhận được từ YouTube."""
        self.logger.debug(f"process_event({event_id}, {event_type}, {args})")

        try:
            self.subscribe_task_watchdog.cancel()
        except:
            pass
        finally:
            self.subscribe_task_watchdog = asyncio.create_task(self._watchdog())

        if event_type == "onStateChange":
            data = args[0]
            if self.mute_ads and data["state"] == "1":
                create_task(self.mute(False, override=True))

        elif event_type == "nowPlaying":
            data = args[0]
            if self.mute_ads and data.get("state", "0") == "1":
                create_task(self.mute(False, override=True))

        elif event_type == "onAdStateChange":
            data = args[0]
            if data["adState"] == "0":
                create_task(self.mute(False, override=True))
            elif self.skip_ads and data["isSkipEnabled"] == "true":
                self.logger.info("Phát hiện quảng cáo, đang bỏ qua...")
                create_task(self.skip_ad())
                create_task(self.mute(False, override=True))
            elif self.mute_ads:
                create_task(self.mute(True, override=True))

        elif event_type == "onVolumeChanged":
            self.volume_state = args[0]

        elif event_type == "autoplayUpNext":
            if len(args) > 0 and (vid_id := args[0]["videoId"]):
                create_task(self.api_helper.get_segments(vid_id))

        elif event_type == "adPlaying":
            data = args[0]
            if vid_id := data["contentVideoId"]:
                create_task(self.api_helper.get_segments(vid_id))
            elif self.skip_ads and data["isSkipEnabled"] == "true":
                self.logger.info("Phát hiện quảng cáo, đang bỏ qua...")
                create_task(self.skip_ad())
                create_task(self.mute(False, override=True))
            elif self.mute_ads:
                create_task(self.mute(True, override=True))

        elif event_type == "loungeStatus":
            data = args[0]
            devices = json.loads(data["devices"])
            for device in devices:
                if device["type"] == "LOUNGE_SCREEN":
                    device_info = json.loads(device.get("deviceInfo", "{}"))
                    if device_info.get("clientName", "") in youtube_client_blacklist:
                        self._sid = None
                        self._gsession = None

        elif event_type == "onSubtitlesTrackChanged":
            if self.shorts_disconnected:
                data = args[0]
                video_id_saved = data.get("videoId", None)
                self.shorts_disconnected = False
                create_task(self.play_video(video_id_saved))

        elif event_type == "loungeScreenDisconnected":
            data = args[0]
            if data["reason"] == "disconnectedByUserScreenInitiated":
                self.shorts_disconnected = True

        elif event_type == "onAutoplayModeChanged":
            create_task(self.set_auto_play_mode(self.auto_play))

        super()._process_event(event_id, event_type, args)

    async def set_volume(self, volume: int) -> None:
        await super()._command("setVolume", {"volume": volume})

    async def mute(self, mute: bool, override: bool = False) -> None:
        mute_str = "true" if mute else "false"
        if override or not (self.volume_state.get("muted", "false") == mute_str):
            self.volume_state["muted"] = mute_str
            await super()._command(
                "setVolume",
                {"volume": self.volume_state.get("volume", 100), "muted": mute_str},
            )

    async def set_auto_play_mode(self, enabled: bool):
        await super()._command(
            "setAutoplayMode", {"autoplayMode": "ENABLED" if enabled else "DISABLED"}
        )

    async def play_video(self, video_id: str) -> bool:
        return await self._command("setPlaylist", {"videoId": video_id})
