# QuestLog
Project for group 4 dev team to make QuestLog

* Run instructions
- First create a virtual environment (python -m venv venv)
- Activate virtual environment
  - Windows (venv\scripts\Activate.ps1)
  - Linux (source venv/bin/activate)
- Install all requirements (pip install -r requirements.txt)

* Running on Windows local testing
- python manage.py runserver

* Running on linux with gunicorn
-  gunicorn config.wsgi:QuestLog

* When reviewing a PR, ensure you review the environment the PR was deployed to. This will ensure the app will deploy properly once merged into main.
