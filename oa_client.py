"""Illustrative rules and an experimental OpenAccountants JSON-RPC adapter.

The live authentication and response contract need integration verification.
Provider metadata is reported without independent attestation.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import json
import os
import urllib.request
import urllib.error

MCP_URL = os.environ.get("OA_MCP_URL", "https://www.openaccountants.com/api/mcp")
MCP_TOKEN = os.environ.get("OA_MCP_TOKEN")


class OAClient:
    def __init__(self, token: str | None = MCP_TOKEN, url: str = MCP_URL):
        self.token, self.url, self._id = token, url, 0

    @property
    def live(self) -> bool:
        return bool(self.token)

    def start(self, intent: str, jurisdiction: str) -> dict:
        if not self.live:
            return deepcopy(_MOCK_START.get(jurisdiction.upper(), _MOCK_START["_DEFAULT"]))
        return self._call("start", {"intent": intent, "jurisdiction": jurisdiction})

    def get_skill(self, slug: str) -> dict:
        if not self.live:
            result = deepcopy(_MOCK_SKILL.get(slug, _MOCK_SKILL["_DEFAULT"]))
        else:
            result = self._call("get_skill", {"slug": slug})
        if not isinstance(result, dict):
            raise ValueError("get_skill must return an object")
        return {**result, "provenance": "provider-reported" if self.live else "sample"}

    def _call(self, tool: str, arguments: dict) -> dict:
        self._id += 1
        body = json.dumps({"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
                           "params": {"name": tool, "arguments": arguments}}).encode()
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"  # scheme TBD; swap if OA uses apikey
        req = urllib.request.Request(self.url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.load(resp, parse_float=Decimal)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"OA MCP HTTP {e.code}") from e
        if not isinstance(payload, dict):
            raise ValueError("OA MCP response must be an object")
        if payload.get("jsonrpc") != "2.0" or type(payload.get("id")) is not int or payload["id"] != self._id:
            raise ValueError("OA MCP response version or request ID does not match")
        if "error" in payload:
            raise RuntimeError("OA MCP returned an error")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise ValueError("OA MCP result must be an object")
        if "isError" in result and not isinstance(result["isError"], bool):
            raise ValueError("OA MCP isError must be a Boolean")
        if result.get("isError"):
            raise RuntimeError("OA MCP tool returned an error")
        if "structuredContent" in result:
            if not isinstance(result["structuredContent"], dict):
                raise ValueError("OA MCP structuredContent must be an object")
            return result["structuredContent"]
        content = result.get("content")
        if not isinstance(content, list) or not content or not isinstance(content[0], dict):
            raise ValueError("OA MCP content must contain a text object")
        if content[0].get("type") != "text" or not isinstance(content[0].get("text"), str):
            raise ValueError("OA MCP content must contain a text string")
        return json.loads(content[0]["text"], parse_float=Decimal)


# Bundled illustrative responses have no professional attestation.

_MOCK_START = {
    "US": {"jurisdiction": "US", "skills_to_load": ["us-sales-tax-rates"],
           "next_action": "Load the skill, then rate each cart by destination."},
    "_DEFAULT": {"jurisdiction": "US", "skills_to_load": ["us-sales-tax-rates"],
                 "next_action": "Load the skill, then rate each cart by destination."},
}

_MOCK_SKILL = {
    "us-sales-tax-rates": {
        "slug": "us-sales-tax-rates",
        "name": "Illustrative US destination rates",
        "jurisdiction": "US", "tier": None, "verifier": None,
        "rules": {
            "schema": "illustrative-rates-v1",
            "rate_unit": "fraction",
            "snapshot": "Illustrative comparison, reviewed 26 September 2026; not a current-rate service",
            "combined_rates": {
                "IL/Chicago": "0.1025",
                "CA/Los Angeles": "0.0975",
                "TX/Austin": "0.0825",
                "OR/Portland": "0",
            },
            "sources": {"CA/Los Angeles": "https://cdtfa.ca.gov/taxes-and-fees/rates.aspx"},
        },
        "source": "https://www.openaccountants.com/skills/us-sales-tax-rates",
    },
    "_DEFAULT": {"slug": "us-sales-tax-rates", "name": "US sales-tax rates",
                 "jurisdiction": "US", "tier": None, "verifier": None, "rules": {},
                 "source": "https://www.openaccountants.com/skills"},
}
