"""Send out an M-SEARCH request and listening for responses."""
import asyncio
import socket
import aiohttp  # Thêm import này để chỉnh sửa User-Agent
import ssdp
import xmltodict
from ssdp import network


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        s.connect(("10.254.254.254", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


# Hàm sửa User-Agent theo JavaScript của bạn
def modify_user_agent(user_agent):
    return user_agent.replace(")", "; Mediapartners-Google)")


class Handler(ssdp.aio.SSDP):
    def __init__(self):
        super().__init__()
        self.devices = []

    def clear(self):
        self.devices = []

    def __call__(self):
        return self

    def response_received(self, response: ssdp.messages.SSDPResponse, addr):
        headers = {k.lower(): v for k, v in response.headers.items()}
        if "location" in headers:
            self.devices.append(headers["location"])


async def find_youtube_app(web_session, url_location):
    headers = {
        "User-Agent": modify_user_agent("Mozilla/5.0 (Linux; Android 10; K) "
                                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                                        "Chrome/132.0.0.0 Mobile Safari/537.36")
    }

    async with web_session.get(url_location, headers=headers) as response:
        headers = response.headers
        response = await response.text()

    data = xmltodict.parse(response)
    name = data["root"]["device"]["friendlyName"]
    handler = Handler()
    handler.clear()
    app_url = headers.get("application-url", "")
    youtube_url = app_url + "YouTube"

    async with web_session.get(youtube_url, headers=headers) as response:
        status_code = response.status
        response = await response.text()

    if status_code == 200:
        data = xmltodict.parse(response)
        data = data["service"]
        screen_id = data["additionalData"]["screenId"]
        return {"screen_id": screen_id, "name": name, "offset": 0}


async def discover():
    bind = None
    search_target = "urn:dial-multiscreen-org:service:dial:1"
    max_wait = 10
    handler = Handler()

    family, addr = network.get_best_family(bind, network.PORT)
    loop = asyncio.get_event_loop()
    ip_address = get_ip()
    connect = loop.create_datagram_endpoint(
        handler, family=family, local_addr=(ip_address, None)
    )
    transport, protocol = await connect

    target = network.MULTICAST_ADDRESS_IPV4, network.PORT

    search_request = ssdp.messages.SSDPRequest(
        "M-SEARCH",
        headers={
            "HOST": "%s:%d" % target,
            "MAN": '"ssdp:discover"',
            "MX": str(max_wait),
            "ST": search_target,
        },
    )

    search_request.sendto(transport, target)

    try:
        await asyncio.sleep(4)
    finally:
        transport.close()

    devices = []

    async with aiohttp.ClientSession(headers={
        "User-Agent": modify_user_agent("Mozilla/5.0 (Linux; Android 10; K) "
                                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                                        "Chrome/132.0.0.0 Mobile Safari/537.36")
    }) as web_session:
        for i in handler.devices:
            device = await find_youtube_app(web_session, i)
            if device:
                devices.append(device)

    return devices
