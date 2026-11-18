import re
import socket
import ssl
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from html.parser import HTMLParser
from http.client import HTTPException, HTTPSConnection
from ipaddress import ip_address
from time import monotonic
from urllib.parse import quote, urljoin, urlsplit

from pydantic import BaseModel, Field


class ResearchClaim(BaseModel):
    subject: str = Field(min_length=5, max_length=180, pattern=r"\S")
    percent: Decimal = Field(ge=-1_000_000, le=1_000_000, max_digits=12)


class PinnedConnection(HTTPSConnection):
    def __init__(self, hostname, address, timeout):
        super().__init__(hostname, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        raw = socket.create_connection((self.address, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def public_address(hostname):
    addresses = [item[4][0] for item in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)]
    if not addresses or any(
        not ip_address(address).is_global or ip_address(address).is_multicast for address in addresses
    ):
        raise ValueError("Source resolves outside the public internet.")
    return addresses[0]


def source_url(url):
    parsed = urlsplit(url)
    if (
        len(url) > 2048
        or not parsed.hostname
        or parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
        or any(ord(character) <= 32 or character == "\\" for character in url)
    ):
        raise ValueError("Source requires a public HTTPS URL on port 443.")
    return parsed


def read_source(url):
    deadline = monotonic() + 8
    for _ in range(3):
        parsed = source_url(url)
        hostname = parsed.hostname.encode("idna").decode("ascii")
        address = public_address(hostname)
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise ValueError("Source read timed out.")
        path = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
        if parsed.query:
            path += "?" + quote(parsed.query, safe="/%:@!$&'()*+,;=?-._~")
        connection = PinnedConnection(hostname, address, min(remaining, 3))
        try:
            connection.request(
                "GET", path, headers={"Accept": "text/html,text/plain", "Accept-Encoding": "identity"}
            )
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308} and response.getheader("Location"):
                url = urljoin(url, response.getheader("Location"))
                continue
            media = response.headers.get_content_type()
            if response.status != 200 or media not in {"text/html", "text/plain"}:
                raise ValueError("Source did not return supported HTML or plain text.")
            if response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("Source returned unsupported content encoding.")
            body = bytearray()
            while chunk := response.read1(32768):
                body.extend(chunk)
                if monotonic() > deadline or len(body) > 750_000:
                    raise ValueError("Source exceeds size or time limits.")
            charset = response.headers.get_content_charset() or "utf-8"
            return url, source_text(body.decode(charset, errors="replace"), media)
        finally:
            connection.close()
    raise ValueError("Too many source redirects.")


class VisibleText(HTMLParser):
    hidden = frozenset({"script", "style", "noscript", "template", "head", "svg"})
    blocks = frozenset({"p", "div", "section", "article", "li", "h1", "h2", "h3", "br", "tr", "td"})

    def __init__(self):
        super().__init__()
        self.omit = []
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self.hidden:
            self.omit.append(tag)
        elif not self.omit and tag in self.blocks:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.omit and self.omit[-1] == tag:
            self.omit.pop()
        elif not self.omit and tag in self.blocks:
            self.parts.append("\n")

    def handle_data(self, value):
        if not self.omit:
            self.parts.append(value)


def source_text(body, media):
    if media == "text/plain":
        return body
    parser = VisibleText()
    parser.feed(body)
    parser.close()
    return "".join(parser.parts)


PERCENT = re.compile(r"(?<![\w.,])([+-]?\d+(?:\.\d+)?)\s*(?:%|percent\b)", re.IGNORECASE)
UNCERTAIN = re.compile(
    r"\b(?:no|not|never|might|could|projected|forecast|target|between|or|approximately|about|excluding)\b",
    re.IGNORECASE,
)


def citations(claim, documents):
    found = []
    subject = " ".join(claim.subject.casefold().split())
    subject_phrase = re.compile(r"(?<!\w)" + re.escape(subject) + r"(?!\w)")
    for source in documents:
        for raw in re.split(r"(?<=[.!?])\s+|\n+", source["text"]):
            excerpt = " ".join(raw.split())
            if (
                len(excerpt) > 450
                or UNCERTAIN.search(excerpt)
                or not subject_phrase.search(excerpt.casefold())
            ):
                continue
            values = PERCENT.findall(excerpt)
            if len(values) != 1:
                continue
            value = Decimal(values[0])
            found.append(
                {
                    "url": source["url"],
                    "title": source["title"],
                    "retrieved_at": source["retrieved_at"],
                    "excerpt": excerpt,
                    "value": str(value),
                    "stance": "supports" if value == claim.percent else "different_value",
                }
            )
            if len(found) >= 25:
                return found
    return found


def verify(sources, claims):
    def retrieve(source):
        try:
            url, body = read_source(source["url"])
        except (ValueError, OSError, HTTPException, LookupError):
            return source | {"read_status": "unavailable"}, None
        metadata = source | {
            "url": url,
            "publisher": urlsplit(url).hostname,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "read_status": "read",
        }
        return metadata, metadata | {"text": body}

    with ThreadPoolExecutor(max_workers=4) as pool:
        retrieved = list(pool.map(retrieve, sources[:4]))
    documents = {doc["url"]: doc for _, doc in retrieved if doc}
    checks = []
    for claim in claims:
        references = citations(claim, list(documents.values()))
        stances = {entry["stance"] for entry in references}
        status = (
            "conflicting"
            if len(stances) == 2
            else "different_value"
            if "different_value" in stances
            else "supported"
            if "supports" in stances
            else "insufficient"
        )
        checks.append({"claim": claim.model_dump(mode="json"), "status": status, "citations": references})
    return [item for item, _ in retrieved] + sources[4:], checks
