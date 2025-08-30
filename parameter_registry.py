class ParameterRegistry:
    """A minimal registry to route parameter updates through a single apply path.

    Each key is registered with two callables:
      - read(): () -> value
      - apply(value, *, transient: bool = False): apply value to Model + UI
    """

    def __init__(self):
        self._entries = {}

    def register(self, key, read_fn, apply_fn):
        if not callable(read_fn) or not callable(apply_fn):
            raise ValueError("read_fn and apply_fn must be callable")
        self._entries[key] = {
            "read": read_fn,
            "apply": apply_fn,
        }

    def has_key(self, key):
        return key in self._entries

    def read(self, key):
        if key not in self._entries:
            raise KeyError(f"Parameter key not registered: {key}")
        return self._entries[key]["read"]()

    def apply(self, key, value, *, transient=False):
        if key not in self._entries:
            raise KeyError(f"Parameter key not registered: {key}")
        self._entries[key]["apply"](value, transient=transient)


