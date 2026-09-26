import json
import urllib.request


class Adapter:
    """Fetches one page of records per call.

    fetch(cursor) -> (records, next_cursor). next_cursor None means done.
    Each record: {"url": str, "content": bytes, "license": str}.
    """

    def fetch(self, cursor):
        raise NotImplementedError


class HttpApiAdapter(Adapter):
    """Generic JSON API adapter: GET endpoint?cursor=<cursor>.

    Expects {"items": [{"url":..., "content":..., "license":...}], "next": ...}.
    """

    def __init__(self, source):
        self.source = source

    def fetch(self, cursor):
        url = self.source.endpoint
        if cursor:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}cursor={cursor}"
        request = urllib.request.Request(url)
        token = self.source.auth_token()
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(request, timeout=60) as resp:
            payload = json.load(resp)
        records = []
        for item in payload.get("items", []):
            content = item.get("content", "")
            if isinstance(content, str):
                content = content.encode("utf-8")
            records.append(
                {
                    "url": item.get("url", ""),
                    "content": content,
                    "license": item.get("license", self.source.license_note),
                }
            )
        return records, payload.get("next")


ADAPTER_TYPES = {"api": HttpApiAdapter}


def build_adapter(source):
    try:
        cls = ADAPTER_TYPES[source.type]
    except KeyError:
        raise ValueError(f"no adapter for source type: {source.type}")
    return cls(source)
