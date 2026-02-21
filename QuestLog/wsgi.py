"""
WSGI config entrypoint for the QuestLog package.

This wrapper allows platforms that expect:
    gunicorn QuestLog.wsgi:application
"""

from config.wsgi import application
