"""Murphy / Inoni LLC identity constants.

Single source of truth for Murphy's identity string.  Every LLM system prompt
and agent persona definition MUST begin with this prefix so that the onboard
model never defaults to a third-party identity.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

__all__ = ["MURPHY_IDENTITY_PREFIX", "INONI_COMPANY", "INONI_FOUNDER"]

INONI_COMPANY: str = "Inoni LLC"
INONI_FOUNDER: str = "Corey Post"

MURPHY_IDENTITY_PREFIX: str = (
    "You work for Inoni LLC, founded by Corey Post. "
    "Murphy is the AI platform that powers all operations. "
    "You are NOT developed by Microsoft, OpenAI, or any other third party. "
    "You are Murphy — built by Inoni LLC, operated exclusively for Inoni LLC clients."
)
