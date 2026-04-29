"""
MurphyTempMail — murphy_tempmail.py
PATCH-154b

Temp email client using mail.tm free API.
Used as fallback when internal SMTP/IMAP can't receive external mail
(e.g. no MX record configured for domain).

Usage:
    async with MurphyTempMail() as tm:
        email, password = tm.address, tm.password
        # ... trigger signup with email ...
        body = await tm.wait_for_email(subject_contains="Stripe", timeout=300)
        links = tm.extract_links(body)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import string
import time
import urllib.request
import urllib.parse
from typing import List, Optional

logger = logging.getLogger("murphy.tempmail")

MAILTM_BASE = "https://api.mail.tm"


def _request(method: str, path: str, data: dict = None, token: str = None) -> dict:
    url = MAILTM_BASE + path
    body = json.dumps(data).encode() if data else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body_err = e.read().decode()
        logger.debug("[TempMail] HTTP %s %s -> %s %s", method, path, e.code, body_err[:200])
        raise


class MurphyTempMail:
    """Async-compatible temp mail client backed by mail.tm."""

    def __init__(self):
        self.address: str = ""
        self.password: str = ""
        self._token: str = ""
        self._account_id: str = ""

    async def __aenter__(self):
        await self.create()
        return self

    async def __aexit__(self, *args):
        await self.delete()

    async def create(self) -> str:
        """Create a new temp mailbox. Returns the email address."""
        loop = asyncio.get_event_loop()

        # Get available domains
        domains = await loop.run_in_executor(None, lambda: _request("GET", "/domains"))
        # API returns list directly or hydra:Collection dict — handle both
        if isinstance(domains, list):
            domain = domains[0]["domain"]
        else:
            domain = domains["hydra:member"][0]["domain"]

        # Generate random address
        rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        self.address = f"{rand}@{domain}"
        self.password = ''.join(random.choices(string.ascii_letters + string.digits, k=16))

        # Create account
        await loop.run_in_executor(None, lambda: _request("POST", "/accounts", {
            "address": self.address,
            "password": self.password,
        }))

        # Get token
        resp = await loop.run_in_executor(None, lambda: _request("POST", "/token", {
            "address": self.address,
            "password": self.password,
        }))
        self._token = resp["token"]
        self._account_id = resp.get("id", "")
        logger.info("[TempMail] Created: %s", self.address)
        return self.address

    async def wait_for_email(
        self,
        subject_contains: str = "",
        from_contains: str = "",
        timeout: int = 300,
        poll: int = 8,
    ) -> Optional[str]:
        """Poll inbox until a matching email arrives. Returns full HTML/text body."""
        loop = asyncio.get_event_loop()
        deadline = time.time() + timeout
        seen = set()

        while time.time() < deadline:
            try:
                msgs = await loop.run_in_executor(
                    None,
                    lambda: _request("GET", "/messages", token=self._token)
                )
                # Same dual-format handling for messages list
                msg_list = msgs if isinstance(msgs, list) else msgs.get("hydra:member", [])
                for msg in msg_list:
                    mid = msg["id"]
                    if mid in seen:
                        continue
                    seen.add(mid)
                    subj = msg.get("subject", "")
                    frm  = msg.get("from", {}).get("address", "")
                    if subject_contains and subject_contains.lower() not in subj.lower():
                        continue
                    if from_contains and from_contains.lower() not in frm.lower():
                        continue
                    # Fetch full message
                    full = await loop.run_in_executor(
                        None,
                        lambda mid=mid: _request("GET", f"/messages/{mid}", token=self._token)
                    )
                    body = full.get("html", [""])[0] or full.get("text", "")
                    logger.info("[TempMail] Got email: subject=%r from=%r", subj, frm)
                    return body
            except Exception as e:
                logger.debug("[TempMail] Poll error: %s", e)

            await asyncio.sleep(poll)

        logger.warning("[TempMail] Timeout waiting for email (subject=%r)", subject_contains)
        return None

    def extract_links(self, html_body: str) -> List[str]:
        """Pull all href links from email body."""
        return re.findall(r'href=["\'](https?://[^"\']+)["\'\']', html_body)

    async def delete(self):
        if not self._account_id:
            return
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: _request("DELETE", f"/accounts/{self._account_id}", token=self._token)
            )
            logger.info("[TempMail] Deleted account %s", self.address)
        except Exception as e:
            logger.debug("[TempMail] Delete failed: %s", e)
