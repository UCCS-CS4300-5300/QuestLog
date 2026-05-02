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

LOGGER = logging.getLogger(__name__)
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

load_dotenv()
# Render can set either API_KEY or GEMINI_API_KEY. Keep API_KEY for the current deploy setup.


LAST_WIZARD_FAILURE = 0
WIZ_BREAK_DURATION = 180


def get_api_key():
    return os.getenv("GEMINI_API_KEY") or os.getenv("API_KEY")


def get_model_name():
    return os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL


def askWizard(name, desc):
    """Return a fantasy title and description, or (None, None) if Gemini is unavailable."""
    global LAST_WIZARD_FAILURE

    current_time = time.time()
    failed_response = (None, None)

    if (current_time - LAST_WIZARD_FAILURE) < WIZ_BREAK_DURATION:
        return failed_response

    api_key = get_api_key()
    if not api_key:
        LOGGER.info("Gemini wizard skipped because API_KEY/GEMINI_API_KEY is not configured.")
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

    model_name = get_model_name()
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
            return failed_response

        if (len(wizard_name) > 120) or (len(wizard_desc) > 500):
            LOGGER.warning("Gemini wizard response was longer than the task field limits.")
            return failed_response

        return (wizard_name, wizard_desc)
    except requests.exceptions.RequestException as exc:
        LAST_WIZARD_FAILURE = time.time()
        status_code = getattr(getattr(exc, "response", None), "status_code", "unknown")
        LOGGER.warning(
            "Gemini wizard request failed for model %s with status %s.",
            model_name,
            status_code,
        )
        return failed_response
    except (KeyError, IndexError, TypeError, ValueError):
        LAST_WIZARD_FAILURE = time.time()
        LOGGER.warning("Gemini wizard returned an unexpected response shape.")
        return failed_response
