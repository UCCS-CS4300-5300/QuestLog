import requests
import json 
import random
import os
from dotenv import load_dotenv
import logging
from django.core.cache import cache  # Import Django's cache


URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
#gemini-flash-latest makes it so if in the future the model being used is discontinued, 
#it will automatically use the latest model



def askWizard (name, desc): 
    #takes the task name and a short description as input
    #prompts gemini to translate it into wizard speak
    #if it fails, it will instead return the a error placeholders in the same form and quest giver being "none"
    #input (task name, task description)
    #output (fantasy task name, fantasy task description)


    if not os.getenv("API_KEY"):
        load_dotenv()
    API_KEY = os.getenv("API_KEY") #this will be None if neither render nor the .env file have the API_KEY
    #need to add "API_KEY" to render or need to have API_KEY=12345678 in .env

    nameFailed = name
    descFailed = ("Sorry it appears some miscreant has vandalized the quest board."
    " Please view the original task to see the description for this quest")
    #if there is no in-app way to view the original task description, change descFailed into desc



    if not API_KEY:
        return (nameFailed, descFailed)
        #don't make a useless call if there is no API key

    random_number = random.randint(1, 4)
    #randomly determine what fantasy character is giving the quest
    #can skew the odds later to make some more common or uncommon for fun
    quest_giver = ""
    match random_number:
        case 1: quest_giver = "The mighty wizard Aeltharion"
        case 2: quest_giver = "The spoiled princess Lysandria"
        case 3: quest_giver = "The humble barkeep Tobias"
        case 4: quest_giver = "The sniveling goblin Gug"
        case _: return (nameFailed, descFailed) #this will never occur
   
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
        response = requests.post(URL, json=payload, headers=headers, timeout=3)
        response.raise_for_status()
        temp = response.json ()
        try: 
            #this try/except block ensures that the response from gemini is in the format we expect
            #it is very unlikely this will ever be the case, but it is good practice
            rawStr = temp['candidates'][0]['content']['parts'][0]['text']
            reply = json.loads(rawStr)
            wizardName = reply['fantasy_task']
            wizardDesc = reply['fantasy_description']
            if (len(wizardName) > 120) or (len(wizardDesc) > 500):
                return (nameFailed, descFailed) 
                #gemini's response was too long. 
                #the prompt gemini receives requests a max length of 50 and 400 characters
                #but this limit is higher just to be safe.

            return (wizardName, wizardDesc)
        except (KeyError, IndexError, TypeError):
            #this handles if the response structure from gemini is unexpected
            return (nameFailed, descFailed)
    except Exception as e:
        #this try/except block handles if we receive an error response from gemini
        #such as no api tokens left or some other error. 
        return (nameFailed, descFailed)
    

    



