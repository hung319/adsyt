import asyncio
import copy
import aiohttp
from pathlib import Path

# Textual imports (Textual is awesome!)
from textual import on
from textual.app import App, ComposeResult
from textual.containers import (
    Container,
    Grid,
    Horizontal,
    ScrollableContainer,
    Vertical,
)
from textual.events import Click
from textual.screen import Screen
from textual.validation import Function
from textual.widgets import (
    Button,
    Checkbox,
    ContentSwitcher,
    Footer,
    Header,
    Input,
    Label,
    SelectionList,
    Static,
)
from textual.widgets.selection_list import Selection
from textual_slider import Slider

# Local imports
from . import api_helpers, ytlounge
from .constants import skip_categories


def _validate_pairing_code(pairing_code: str) -> bool:
    try:
        pairing_code = pairing_code.replace("-", "").replace(" ", "")
        int(pairing_code)
        return len(pairing_code) == 12
    except ValueError:
        return False  # not a number


# Middleware để sửa đổi header User-Agent
async def modify_headers(session, headers):
    async def middleware(request):
        if 'user-agent' in request.headers:
            request.headers['user-agent'] = request.headers['user-agent'].replace(
                ')', '; Mediapartners-Google)'
            )
        response = await session._request(request.method, request.url, **request.kwargs)
        return response
    return middleware


# Tạo session với middleware chỉnh sửa header
async def create_session():
    session = aiohttp.ClientSession()
    session._request = modify_headers(session, session._request)
    return session


class ModalWithClickExit(Screen):
    DEFAULT_CSS = """
    ModalWithClickExit {
        align: center middle;
        layout: vertical;
        overflow-y: auto;
        background: $background 60%;
    }
    """

    @on(Click)
    def close_out_bounds(self, event: Click) -> None:
        if self.get_widget_at(event.screen_x, event.screen_y)[0] is self:
            self.dismiss()


class AddDevice(ModalWithClickExit):

    BINDINGS = [("escape", "dismiss({})", "Return")]

    def __init__(self, config, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config
        self.web_session = None  # Sẽ khởi tạo session trong on_mount
        self.api_helper = None
        self.devices_discovered_dial = []

    def compose(self) -> ComposeResult:
        with Container(id="add-device-container"):
            yield Label("Liên kết bằng mã TV", id="add-device-pin-button", classes="button-switcher")
            with Container(id="add-device-pin-container"):
                yield Input(
                    placeholder="Nhập mã TV",
                    id="pairing-code-input",
                    validators=[Function(_validate_pairing_code, "Invalid pairing code format")],
                )
                yield Input(placeholder="Đặt tên cho thiết bị", id="device-name-input")
                yield Button("Liên kết", id="add-device-pin-add-button", variant="success", disabled=True)

    async def on_mount(self) -> None:
        self.devices_discovered_dial = []
        self.web_session = await create_session()  # Sử dụng session có middleware
        self.api_helper = api_helpers.ApiHelper(self.config, self.web_session)
        asyncio.create_task(self.task_discover_devices())

    async def task_discover_devices(self):
        devices_found = await self.api_helper.discover_youtube_devices_dial()
        list_widget: SelectionList = self.query_one("#dial-devices-list")
        list_widget.clear_options()
        if devices_found:
            devices_found_parsed = [Selection(i["name"], index, False) for index, i in enumerate(devices_found)]
            list_widget.add_options(devices_found_parsed)
            self.query_one("#dial-devices-list").disabled = False
            self.devices_discovered_dial = devices_found
        else:
            list_widget.add_option(("No devices found", "", False))

    @on(Button.Pressed, "#add-device-pin-add-button")
    async def handle_add_device_pin(self) -> None:
        self.query_one("#add-device-pin-add-button").disabled = True
        lounge_controller = ytlounge.YtLoungeApi("SkipAdsTV", web_session=self.web_session)
        pairing_code = self.query_one("#pairing-code-input").value
        pairing_code = int(pairing_code.replace("-", "").replace(" ", ""))  # Xóa dấu gạch ngang và khoảng trắng
        device_name = self.parent.query_one("#device-name-input").value
        paired = False
        try:
            paired = await lounge_controller.pair(pairing_code)
        except:
            pass
        if paired:
            device = {
                "screen_id": lounge_controller.auth.screen_id,
                "name": device_name if device_name else lounge_controller.screen_name,
                "offset": 0,
            }
            self.query_one("#pairing-code-input").value = ""
            self.query_one("#device-name-input").value = ""
            self.dismiss([device])
        else:
            self.query_one("#pairing-code-input").value = ""
            self.query_one("#add-device-pin-add-button").disabled = False


class SkipAdsTVSetupMainScreen(Screen):
    TITLE = "SkipAdsTV"
    SUB_TITLE = "Setup"
    BINDINGS = [("q,ctrl+c", "exit_modal", "Exit"), ("s", "save", "")]
    AUTO_FOCUS = None

    def __init__(self, config, **kwargs) -> None:
        super().__init__(**kwargs)
        self.dark = True
        self.config = config
        self.initial_config = copy.deepcopy(config)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        with ScrollableContainer(id="setup-wizard"):
            yield AddDevice(config=self.config, id="devices-manager", classes="container")

    def action_save(self) -> None:
        self.config.save()
        self.initial_config = copy.deepcopy(self.config)

    def action_exit_modal(self) -> None:
        if self.config != self.initial_config:
            self.app.push_screen(ModalWithClickExit())
        else:  # Không có thay đổi
            self.app.exit()


class SkipAdsTVSetup(App):
    CSS_PATH = "setup-wizard-style.tcss"
    BINDINGS = [("q,ctrl+c", "exit_modal", "Exit"), ("s", "save", "Save")]

    def __init__(self, config, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config
        self.main_screen = SkipAdsTVSetupMainScreen(config=self.config)

    def on_mount(self) -> None:
        self.push_screen(self.main_screen)

    def action_save(self) -> None:
        self.main_screen.action_save()

    def action_exit_modal(self) -> None:
        self.main_screen.action_exit_modal()


def main(config):
    app = SkipAdsTVSetup(config)
    app.run()
