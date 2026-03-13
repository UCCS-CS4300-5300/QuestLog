# QuestLog

QuestLog is a Django application for tracking tasks and user progress with account registration, login, and profile management.

## Live Deployment

All deployed environments for this project are hosted on Render.

Primary Render URL: https://questlog-khx0.onrender.com

## Current Capabilities

- Public pages for `home`, `about`, `tasks`, and `complete_task`
- Account registration with username, password, email, display name, and optional profile picture
- Account login with safe redirect handling
- Auth-protected profile page
- User profile storage backed by Django `auth.User` plus a `UserProfile` record
- Static asset support and local media support while `DEBUG=True`
- Automated Django tests, behave tests, coverage reporting, and CI checks

## Local Setup

1. Create a virtual environment.

```powershell
python -m venv venv
```

2. Activate it.

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Linux:

```bash
source venv/bin/activate
```

3. Install dependencies.

```bash
pip install -r requirements.txt
```

4. Apply migrations.

```bash
python manage.py migrate
```

## Running Locally

Default local run:

```bash
python manage.py runserver
```

Gunicorn run on Linux:

```bash
gunicorn config.wsgi:QuestLog
```

## Temporary Debug Mode

`DEBUG` is production-safe by default and stays `False` unless `DJANGO_DEBUG` is explicitly set to a truthy value such as `1`, `true`, `yes`, or `on`.

Use this only for temporary local testing.

Windows PowerShell:

```powershell
$env:DJANGO_DEBUG = "1"
python manage.py runserver
```

Clear it after testing:

```powershell
Remove-Item Env:\DJANGO_DEBUG
```

Linux:

```bash
export DJANGO_DEBUG=1
python manage.py runserver
```

Clear it after testing:

```bash
unset DJANGO_DEBUG
```

One-command Linux option:

```bash
DJANGO_DEBUG=1 python manage.py runserver
```

## Render Deployment

Render is the deployment target for this project.

- Build script: [`build.sh`](build.sh)
- Build steps:
  - `pip install -r requirements.txt`
  - `python manage.py collectstatic --no-input`
  - `python manage.py migrate`
- Render hostname support is wired through `RENDER_EXTERNAL_HOSTNAME`
- Keep `DJANGO_DEBUG` unset or set to `0` in Render so production stays non-debug

## Testing

Run Django tests:

```bash
python manage.py test QuestLog
```

Run behave tests:

```bash
python manage.py behave
```

Run Django system checks:

```bash
python manage.py check
```

Run coverage the same way CI does:

```bash
coverage erase
coverage run --source=QuestLog,config manage.py test
coverage run --append --source=QuestLog,config manage.py behave --simple
coverage report -m --skip-empty
```

## Test Case Annotations

### Django test suite

File: [`QuestLog/tests.py`](QuestLog/tests.py)

- `ViewReachabilityTests`
  - Confirms named routes exist and return expected status codes
  - Verifies anonymous access to `/profile/` redirects to login
- `DeploymentEntrypointTests`
  - Confirms WSGI and ASGI entrypoints expose application objects correctly
- `SettingsBranchCoverageTests`
  - Verifies `DEBUG=False` by default
  - Verifies explicit `DJANGO_DEBUG=1` enables development behavior
  - Verifies Render hostnames are added to `ALLOWED_HOSTS`
- `UrlConfigurationTests`
  - Verifies media URLs are not served when `DEBUG=False`
  - Verifies media URLs are available only when `DEBUG=True`
- `UserProfileTests`
  - Verifies the project uses Django `auth.User`
  - Verifies a `UserProfile` is created and stores display-name/profile-picture data
- `AuthenticationFlowTests`
  - Verifies registration, login, authenticated redirects, safe `next` handling, and profile rendering
  - Covers missing profile pictures and missing profile recovery

### Behave feature suite

Files:

- [`features/smoke.feature`](features/smoke.feature)
- [`features/user_model.feature`](features/user_model.feature)

Coverage:

- Smoke checks for core pages
- Account creation flow
- Login flow
- Authenticated profile access
- Profile picture persistence through behavior scenarios

### Coverage configuration

File: [`.coveragerc`](.coveragerc)

- Coverage is focused on application code in `QuestLog` and `config`
- Test files are intentionally omitted from coverage totals

## CI

GitHub Actions runs the following on pushes and pull requests:

- Django unit tests
- behave tests
- coverage report generation
- `python manage.py check`
- AI-assisted pull request review workflow

Workflow files:

- [`.github/workflows/django_ci.yml`](.github/workflows/django_ci.yml)
- [`.github/workflows/ai_reviewer.yml`](.github/workflows/ai_reviewer.yml)
