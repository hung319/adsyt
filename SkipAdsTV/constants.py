userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; Mediapartners-Google/2.1; +http://www.google.com/bot.html) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
SponsorBlock_service = "youtube"
SponsorBlock_actiontype = "skip"

SponsorBlock_api = "https://sponsor.ajay.app/api/"
Youtube_api = "https://www.googleapis.com/youtube/v3/"

skip_categories = (
    ("Sponsor", "sponsor"),
    ("Self Promotion", "selfpromo"),
    ("Intro", "intro"),
    ("Outro", "outro"),
    ("Music Offtopic", "music_offtopic"),
    ("Interaction", "interaction"),
    ("Exclusive Access", "exclusive_access"),
    ("POI Highlight", "poi_highlight"),
    ("Preview", "preview"),
    ("Filler", "filler"),
)

youtube_client_blacklist = ["TVHTML5_FOR_KIDS"]


config_file_blacklist_keys = ["config_file", "data_dir"]
