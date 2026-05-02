"""
This module is the main logic for the wizard rewording of tasks.
"""

import os
import json
import logging
import random
import time

import requests
from dotenv import load_dotenv
from django.utils.html import strip_tags
from django.conf import settings

LOGGER = logging.getLogger(__name__)
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

load_dotenv()
# Render can set either API_KEY or GEMINI_API_KEY. Keep API_KEY for the current deploy setup.


LAST_WIZARD_FAILURE = 0
LAST_WIZARD_FAILURE_REASON = ""
WIZ_BREAK_DURATION = 180


def remember_failure(reason, use_cooldown=True):
    global LAST_WIZARD_FAILURE
    global LAST_WIZARD_FAILURE_REASON

    LAST_WIZARD_FAILURE_REASON = reason
    if use_cooldown:
        LAST_WIZARD_FAILURE = time.time()


def askWizard(name, desc):
    """Return a fantasy title and description, or (None, None) if Gemini is unavailable."""
    current_time = time.time()
    failed_response = (None, None)

    if (current_time - LAST_WIZARD_FAILURE) < WIZ_BREAK_DURATION:
        LOGGER.warning(
            "Gemini wizard skipped because it is cooling down after a previous failure: %s",
            LAST_WIZARD_FAILURE_REASON or "unknown reason",
        )
        return failed_response

    api_key = settings.GEMINI_API_KEY if settings.GEMINI_API_KEY is not None else os.environ.get('API_KEY')
    if not api_key:
        reason = "API_KEY/GEMINI_API_KEY/GOOGLE_API_KEY is not configured."
        remember_failure(reason, use_cooldown=False)
        LOGGER.warning("Gemini wizard skipped because %s", reason)
        return failed_response

    random_number = random.randint(1, 4)

    quest_givers = {
        1: "The mighty wizard Aeltharion",
        2: "The spoiled princess Lysandria",
        3: "The humble barkeep Tobias",
        4: "The sniveling goblin Gug",
    }
    quest_giver = quest_givers.get(random_number)

    prompt = f"""
    You are a {quest_giver} from a fantasy world.
    Translate the following modern task into a fantasy quest
    that you have posted to the public and requested to be completed.
    Please make sure to say your name in the description somewhere.

    Task Name: {name}
    Description: {desc}

    Keep the new task name under 50 characters long
    and keep the new task description under 400 characters long.
    Return your response ONLY as a JSON object with these keys:
    "fantasy_task": "The title of the quest",
    "fantasy_description": "The description of the quest"
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": {
                "type": "object",
                "properties": {
                    "fantasy_task": {"type": "string"},
                    "fantasy_description": {"type": "string"},
                },
                "required": ["fantasy_task", "fantasy_description"],
                "propertyOrdering": ["fantasy_task", "fantasy_description"],
            },
        },
    }

    model_name = DEFAULT_GEMINI_MODEL
    request_url = URL_TEMPLATE.format(model=model_name)
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}

    try:
        response = requests.post(request_url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        response_data = response.json()
        raw_response = response_data["candidates"][0]["content"]["parts"][0]["text"]
        reply = json.loads(raw_response)
        wizard_name = strip_tags(str(reply["fantasy_task"])).strip()
        wizard_desc = strip_tags(str(reply["fantasy_description"])).strip()

        if (not wizard_name) or (not wizard_desc):
            remember_failure("Gemini wizard returned an empty fantasy title or description.")
            LOGGER.warning("Gemini wizard returned an empty fantasy title or description.")
            return failed_response

        if (len(wizard_name) > 120) or (len(wizard_desc) > 5000):
            reason = "Gemini wizard response was longer than the task field limits."
            remember_failure(reason, use_cooldown=False)
            LOGGER.warning("%s", reason)
            return failed_response

        return (wizard_name, wizard_desc)
    except requests.exceptions.RequestException as exc:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", "unknown")
        response_preview = ""
        if response is not None:
            response_preview = response.text.replace("\n", " ")[:500]

        reason = (
            f"Gemini request failed for model {model_name} with status {status_code}. "
            f"{response_preview}"
        ).strip()
        remember_failure(reason)
        LOGGER.warning(
            "Gemini wizard request failed for model %s with status %s. Response: %s",
            model_name,
            status_code,
            response_preview,
        )
        return failed_response
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        reason = f"Gemini wizard returned an unexpected response shape: {exc}"
        remember_failure(reason)
        LOGGER.warning("%s", reason)
        return failed_response
