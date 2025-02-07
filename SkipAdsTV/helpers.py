import argparse
import json
import logging
import os
import sys
import time

from appdirs import user_data_dir

from . import config_setup, main, setup_wizard
from .constants import config_file_blacklist_keys


class Device:
    def __init__(self, args_dict):
        self.screen_id = ""
        self.offset = 0
        self.__load(args_dict)
        self.__validate()

    def __load(self, args_dict):
        for i in args_dict:
            setattr(self, i, args_dict[i])
        # Change offset to seconds (from milliseconds)
        self.offset = self.offset / 1000

    def __validate(self):
        if not self.screen_id:
            raise ValueError("No screen id found")


class Config:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.config_file = os.path.join(data_dir, "config.json")

        self.devices = []
        self.apikey = ""
        self.skip_categories = []  # Categories to skip from the config file
        self.channel_whitelist = []
        self.skip_count_tracking = True
        self.mute_ads = True
        self.skip_ads = True
        self.auto_play = True
        self.__load()

    def validate(self):
        if hasattr(self, "atvs"):
            print("Exiting in 10 seconds...")
            time.sleep(10)
            sys.exit()
        if not self.devices:
            print("No devices found, please add at least one device")
            print("Exiting in 10 seconds...")
            time.sleep(10)
            sys.exit()
        self.devices = [Device(i) for i in self.devices]
        if not self.apikey and self.channel_whitelist:
            raise ValueError(
                "No YouTube API key found and channel whitelist is not empty"
            )
        if not self.skip_categories:
            self.skip_categories = [
                "Sponsor", "sponsor", "Self Promotion", "selfpromo",
                "Intro", "intro", "Outro", "outro", "Music Offtopic",
                "music_offtopic", "Interaction", "interaction",
                "Exclusive Access", "exclusive_access", "POI Highlight",
                "poi_highlight", "Preview", "preview", "Filler", "filler"
            ]
            print("SkipAdsTV: Đã hoàn tất thiết lập")

    def __load(self):
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                for i in config:
                    if i not in config_file_blacklist_keys:
                        setattr(self, i, config[i])
        except FileNotFoundError:
            print("Could not load config file")

    def save(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            config_dict = self.__dict__.copy()
            # Don't save the config file path and data directory
            del config_dict["config_file"]
            del config_dict["data_dir"]
            json.dump(config_dict, f, indent=4)
            print("Config saved successfully.")

    def __eq__(self, other):
        if isinstance(other, Config):
            return self.__dict__ == other.__dict__
        return False


def app_start():
    # If env has a data dir use that, otherwise use the default
    default_data_dir = os.getenv("iSPBTV_data_dir") or user_data_dir(
        "SkipAdsTV", "dmunozv04"
    )
    parser = argparse.ArgumentParser(description="SkipAdsTV")
    parser.add_argument(
        "--data-dir", "-d", default=default_data_dir, help="Data directory"
    )
    parser.add_argument(
        "--setup", "-s", action="store_true", help="Setup the program graphically"
    )
    parser.add_argument(
        "--setup-cli",
        "-sc",
        action="store_true",
        help="Setup the program in the command line",
    )
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    parser.add_argument(
        "--reset-config", "-r", action="store_true", help="Delete old config file"
    )
    args = parser.parse_args()

    # Xóa file config nếu có tùy chọn --reset-config
    config_file_path = os.path.join(args.data_dir, "config.json")
    if args.reset_config:
        if os.path.exists(config_file_path):
            os.remove(config_file_path)
            print("Config file deleted successfully.")
        else:
            print("No config file found to delete.")

    config = Config(args.data_dir)
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    if args.setup:  # Set up the config file graphically
        setup_wizard.main(config)
        sys.exit()
    if args.setup_cli:  # Set up the config file
        config_setup.main(config, args.debug)
    else:
        config.validate()
        main.main(config, args.debug)
