userAgent = "Mozilla/5.0 (compatible; Mediapartners-Google; MSIE 10.0; Windows Phone 8.0; Trident/6.0; IEMobile/10.0; ARM; Touch; NOKIA; Lumia 920)"
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
