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
    RadioButton,
    RadioSet,
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


class Element(Static):

    def __init__(self, element: dict, tooltip: str = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.element_data = element
        self.element_name = ""
        self.process_values_from_data()
        self.tooltip = tooltip

    def process_values_from_data(self):
        pass

    def compose(self) -> ComposeResult:
        yield Button(
            label=self.element_name,
            classes="element-name",
            disabled=True,
            id="element-name",
        )
        yield Button(
            "Xóa", classes="element-remove", variant="error", id="element-remove"
        )

    def on_mount(self) -> None:
        if self.tooltip:
            self.query_one(".element-name").tooltip = self.tooltip
            self.query_one(".element-name").disabled = False


class Device(Element):
    def process_values_from_data(self):
        print(self.element_data)
        if "name" in self.element_data and self.element_data["name"]:
            self.element_name = self.element_data["name"]
        else:
            self.element_name = (
                "Unnamed device with id "
                f"{self.element_data['screen_id'][:5]}..."
                f"{self.element_data['screen_id'][-5:]}"
            )


class ExitScreen(ModalWithClickExit):

    BINDINGS = [
        ("escape", "dismiss()", "Cancel"),
        ("s", "save", "Save"),
        ("q,ctrl+c", "exit", "Exit"),
    ]
    AUTO_FOCUS = "#exit-save"

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(
                "Cấu hình chưa được lưu. Bạn có muốn thoát?",
                id="question",
                classes="button-100",
            ),
            Button("Lưu và Thoát", variant="success", id="exit-save", classes="button-100"),
            Button("Hủy", variant="primary", id="exit-cancel", classes="button-100"),
            id="dialog-exit",
        )

    def action_exit(self) -> None:
        self.app.exit()

    def action_save(self) -> None:
        self.app.config.save()
        self.app.exit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "exit-no-save":
            self.app.exit()
        elif event.button.id == "exit-save":
            self.app.config.save()
            Path('re').touch()
            self.app.exit()
        else:
            self.app.pop_screen()


class AddDevice(ModalWithClickExit):

    BINDINGS = [("escape", "dismiss({})", "Return")]

    def __init__(self, config, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config
        self.web_session = aiohttp.ClientSession()
        self.api_helper = api_helpers.ApiHelper(config, self.web_session)
        self.devices_discovered_dial = []

    def compose(self) -> ComposeResult:
        with Container(id="add-device-container"):
            with Grid(id="add-device-switch-buttons"):
                yield Label(
                    "Liên kết bằng mã TV",
                    id="add-device-pin-button",
                    classes="button-switcher",
                )
            with ContentSwitcher(
                id="add-device-switcher", initial="add-device-pin-container"
            ):
                with Container(id="add-device-pin-container"):
                    yield Input(
                        placeholder=(
                            "Nhập mã TV"
                        ),
                        id="pairing-code-input",
                        validators=[
                            Function(
                                _validate_pairing_code, "Invalid pairing code format"
                            )
                        ],
                    )
                    yield Input(
                        placeholder="Đặt tên cho thiết bị",
                        id="device-name-input",
                    )
                    yield Button(
                        "Liên kết",
                        id="add-device-pin-add-button",
                        variant="success",
                        disabled=True,
                    )

    async def on_mount(self) -> None:
        self.devices_discovered_dial = []
        asyncio.create_task(self.task_discover_devices())

    async def task_discover_devices(self):
        devices_found = await self.api_helper.discover_youtube_devices_dial()
        list_widget: SelectionList = self.query_one("#dial-devices-list")
        list_widget.clear_options()
        if devices_found:
            # print(devices_found)
            devices_found_parsed = []
            for index, i in enumerate(devices_found):
                devices_found_parsed.append(Selection(i["name"], index, False))
            list_widget.add_options(devices_found_parsed)
            self.query_one("#dial-devices-list").disabled = False
            self.devices_discovered_dial = devices_found
        else:
            list_widget.add_option(("No devices found", "", False))

    @on(Button.Pressed, "#add-device-switch-buttons > *")
    def handle_switch_buttons(self, event: Button.Pressed) -> None:
        self.query_one("#add-device-switcher").current = event.button.id.replace(
            "-button", "-container"
        )

    @on(Input.Changed, "#pairing-code-input")
    def changed_pairing_code(self, event: Input.Changed):
        self.query_one("#add-device-pin-add-button").disabled = (
            not event.validation_result.is_valid
        )

    @on(Input.Submitted, "#pairing-code-input")
    @on(Button.Pressed, "#add-device-pin-add-button")
    async def handle_add_device_pin(self) -> None:
        self.query_one("#add-device-pin-add-button").disabled = True
        lounge_controller = ytlounge.YtLoungeApi(
            "SkipAdsTV", web_session=self.web_session
        )
        pairing_code = self.query_one("#pairing-code-input").value
        pairing_code = int(
            pairing_code.replace("-", "").replace(" ", "")
        )  # remove dashes and spaces
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

    @on(Button.Pressed, "#add-device-dial-add-button")
    def handle_add_device_dial(self) -> None:
        list_widget: SelectionList = self.query_one("#dial-devices-list")
        selected_devices = list_widget.selected
        devices = []
        for i in selected_devices:
            devices.append(self.devices_discovered_dial[i])
        self.dismiss(devices)

    @on(SelectionList.SelectedChanged, "#dial-devices-list")
    def changed_device_list(self, event: SelectionList.SelectedChanged):
        self.query_one("#add-device-dial-add-button").disabled = (
            not event.selection_list.selected
        )

class DevicesManager(Vertical):

    def __init__(self, config, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config
        self.devices = config.devices

    def compose(self) -> ComposeResult:
        yield Label("Thiết bị", classes="title")
        with Horizontal(id="add-device-button-container"):
            yield Button("Thêm thiết bị", id="add-device", classes="button-100")
        for device in self.devices:
            yield Device(device)

    def new_devices(self, device_data) -> None:
        if device_data:
            device_widget = None
            for i in device_data:
                self.devices.append(i)
                device_widget = Device(i, tooltip="Click to edit")
                self.mount(device_widget)
            device_widget.focus(scroll_visible=True)

    @staticmethod
    def edit_device(device_widget: Element) -> None:
        device_widget.process_values_from_data()
        device_widget.query_one("#element-name").label = device_widget.element_name

    @on(Button.Pressed, "#element-remove")
    def remove_channel(self, event: Button.Pressed):
        channel_to_remove: Element = event.button.parent
        self.config.devices.remove(channel_to_remove.element_data)
        channel_to_remove.remove()

    @on(Button.Pressed, "#add-device")
    def add_device(self, event: Button.Pressed):
        self.app.push_screen(AddDevice(self.config), callback=self.new_devices)

    @on(Button.Pressed, "#element-name")
    def edit_channel(self, event: Button.Pressed):
        channel_to_edit: Element = event.button.parent
        self.app.push_screen(EditDevice(channel_to_edit), callback=self.edit_device)


class AdSkipMuteManager(Vertical):

    def __init__(self, config, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config

    def compose(self) -> ComposeResult:
        yield Label("Skip/Mute ads", classes="title")
        yield Label(
            (
                "This feature allows you to automatically mute and/or skip native"
                " YouTube ads. Skipping ads only works if that ad shows the 'Skip Ad'"
                " button, if it doesn't then it will only be able to be muted."
            ),
            classes="subtitle",
            id="skip-count-tracking-subtitle",
        )
        with Horizontal(id="ad-skip-mute-container"):
            yield Checkbox(
                value=self.config.skip_ads,
                id="skip-ads-switch",
                label="Enable skipping ads",
            )
            yield Checkbox(
                value=self.config.mute_ads,
                id="mute-ads-switch",
                label="Enable muting ads",
            )

    @on(Checkbox.Changed, "#mute-ads-switch")
    def changed_mute(self, event: Checkbox.Changed):
        self.config.mute_ads = True

    @on(Checkbox.Changed, "#skip-ads-switch")
    def changed_skip(self, event: Checkbox.Changed):
        self.config.skip_ads = True


class AutoPlayManager(Vertical):

    def __init__(self, config, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config

    def compose(self) -> ComposeResult:
        yield Label("Tự động phát video", classes="title")
        yield Label(
            "Nếu được bât, chương trình sẽ tự động phát video kế tiếp",
            classes="subtitle",
            id="autoplay-subtitle",
        )
        with Horizontal(id="autoplay-container"):
            yield Checkbox(
                value=self.config.auto_play,
                id="autoplay-switch",
                label="Bật/Tắt",
            )

    @on(Checkbox.Changed, "#autoplay-switch")
    def changed_skip(self, event: Checkbox.Changed):
        self.config.auto_play = event.checkbox.value


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
            yield DevicesManager(
                config=self.config, id="devices-manager", classes="container"
            )
            yield AutoPlayManager(
                config=self.config, id="autoplay-manager", classes="container"
            )

    def on_mount(self) -> None:
        if self.check_for_old_config_entries():
            self.app.push_screen(MigrationScreen())
            pass

    def action_save(self) -> None:
        self.config.save()
        self.initial_config = copy.deepcopy(self.config)

    def action_exit_modal(self) -> None:
        if self.config != self.initial_config:
            self.app.push_screen(ExitScreen())
        else:  # No changes were made
            self.app.exit()

    def check_for_old_config_entries(self) -> bool:
        if hasattr(self.config, "atvs"):
            return True
        return False

    @on(Input.Changed, "#api-key-input")
    def changed_api_key(self, event: Input.Changed):
        try:  # ChannelWhitelist might not be mounted
            # Show if no api key is set and at least one channel is in the whitelist
            self.app.query_one("#warning-no-key").display = (
                not event.input.value
            ) and self.config.channel_whitelist
        except:
            pass


class SkipAdsTVSetup(App):
    CSS_PATH = (  # tcss is the recommended extension for textual css files
        "setup-wizard-style.tcss"
    )
    # Bindings for the whole app here, so they are available in all screens
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
