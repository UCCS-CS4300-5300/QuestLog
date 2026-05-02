import requests
import json 
import random
import os
import time
from dotenv import load_dotenv
from django.core.cache import cache
from django.utils.html import strip_tags #clean data


URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
#gemini-flash-latest makes it so if in the future the model being used is discontinued, 
#it will automatically use the latest model

load_dotenv()
API_KEY = os.getenv("API_KEY") #this will be None if neither render nor the .env file have the API_KEY
#need to add "API_KEY" to render or need to have API_KEY=12345678 in .env


LAST_WIZARD_FAILURE = 0 #0 means no most recent failure
WIZ_BREAK_DURATION = 180 #if the wizard isn't working, disable it for 3 minutes



def askWizard (name, desc): 
    #takes the task name and a short description as input
    #prompts gemini to translate it into wizard speak
    #if it fails, it will instead return (None, None)
    #input (task name, task description)
    #output (fantasy task name, fantasy task description)

    global LAST_WIZARD_FAILURE

    currentTime = time.time()
    
    nameFailed = None
    descFailed = None
    #These are None to prevent repeat text showing up in task ui



    if (not API_KEY) or ((currentTime - LAST_WIZARD_FAILURE) < WIZ_BREAK_DURATION):
        return (nameFailed, descFailed)
        #don't make a useless call if there is no API key or if the wizard isn't working

    random_number = random.randint(1, 4)
    #randomly determine what fantasy character is giving the quest
    #can skew the odds later to make some more common or uncommon for fun

    quest_givers = {
        1: "The mighty wizard Aeltharion",
        2: "The spoiled princess Lysandria",
        3: "The humble barkeep Tobias",
        4: "The sniveling goblin Gug"
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
            "response_mime_type": "application/json"
        }
    }


    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": API_KEY
    } #Using a header like this should help keep the API key more secure. 

    try:
        response = requests.post(URL, json=payload, headers=headers, timeout=2)
        response.raise_for_status()
        temp = response.json ()
        try: 
            #this try/except block ensures that the response from gemini is in the format we expect
            #it is very unlikely this will ever be the case, but it is good practice
            rawStr = temp['candidates'][0]['content']['parts'][0]['text']
            reply = json.loads(rawStr)
            wizardName = strip_tags(reply['fantasy_task'])
            wizardDesc = strip_tags(reply['fantasy_description'])
            if (len(wizardName) >= 120) or (len(wizardDesc) >= 500):
                return (nameFailed, descFailed) 
                #gemini's response was too long. 
                #the prompt gemini receives requests a max length of 50 and 400 characters
                #but this limit is higher just to be safe.
                #do not flag wizard as not working since it still works
            return (wizardName, wizardDesc)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            #this handles if the response structure from gemini is unexpected
            LAST_WIZARD_FAILURE = time.time()
            return (nameFailed, descFailed)
    except requests.exceptions.RequestException:
        #this code functionally does nothing because of the next except Exception block
        #but separating it out can help with potential future debugging
        LAST_WIZARD_FAILURE = time.time()
        return (nameFailed, descFailed)
    except Exception:
        #this try/except block handles if we receive an error response from gemini
        #such as no api tokens left or some other error. 
        LAST_WIZARD_FAILURE = time.time()
        return (nameFailed, descFailed)
    

    



