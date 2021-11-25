# The SHOW_SETUP variable will decide whether the /setup page will be shown on your instance
# This page might be useful if you are just getting started with webmentions for the first time
# If you  need the setup page, set SHOW_SETUP to True
# I keep mine at False since as I run an instance that is only for me

import os

ROOT_DIRECTORY = os.path.dirname(os.path.abspath("__init__.py"))

RSS_DIRECTORY = "/home/capjamesg/webmention_receiver"

SQLALCHEMY_DATABASE_URI = 'sqlite:///webmentions.db'
SQLALCHEMY_TRACK_MODIFICATIONS = False

CALLBACK_URL = "http://localhost:5000/callback"
CLIENT_ID = "http://localhost:5001/"
TOKEN_ENDPOINT = "http://localhost:5000/token"
AUTH_ENDPOINT = "http://localhost:5000/auth"
ME = "https://jamesg.blog/"

SHOW_SETUP = False

SECRET_KEY = "EXAMPLE SECRET KEY"

WEBHOOK_SERVER = True
WEBHOOK_URL = ""
WEBHOOK_API_KEY = ""