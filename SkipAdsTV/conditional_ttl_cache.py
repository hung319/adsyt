import datetime

from cache.key import KEY
from cache.lru import LRU

class AsyncConditionalTTL:
    class _TTL(LRU):
        def __init__(self, time_to_live, maxsize):
            super().__init__(maxsize=maxsize)

            self.time_to_live = (
                datetime.timedelta(seconds=time_to_live) if time_to_live else None
            )

            self.maxsize = maxsize

        def __contains__(self, key):
            if key not in self.keys():
                return False
            key_expiration = super().__getitem__(key)[1]
            if key_expiration and key_expiration < datetime.datetime.now():
                del self[key]
                return False
            return True

        def __getitem__(self, key):
            value = super().__getitem__(key)[0]
            return value

        def __setitem__(self, key, value):
            value, ignore_ttl = value  # unpack tuple
            ttl_value = (
                (datetime.datetime.now() + self.time_to_live)
                if (self.time_to_live and not ignore_ttl)
                else None
            )  # ignore ttl if ignore_ttl is True
            super().__setitem__(key, (value, ttl_value))

    def __init__(self, time_to_live=60, maxsize=1024, skip_args: int = 0):
        """

        :param time_to_live: Use time_to_live as None for non expiring cache
        :param maxsize: Use maxsize as None for unlimited size cache
        :param skip_args: Use `1` to skip first arg of func in determining cache key
        """
        self.ttl = self._TTL(time_to_live=time_to_live, maxsize=maxsize)
        self.skip_args = skip_args

    def __call__(self, func):
        async def wrapper(*args, **kwargs):
            key = KEY(args[self.skip_args :], kwargs)
            if key in self.ttl:
                val = self.ttl[key]
            else:
                self.ttl[key] = await func(*args, **kwargs)
                val = self.ttl[key]

            return val

        wrapper.__name__ += func.__name__

        return wrapper
