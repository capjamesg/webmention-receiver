# Production values should be uncommented
# I like to comment certain values when I am programming locally so that everything works on my local machine

# The SHOW_SETUP variable will decide whether the /setup page will be shown on your instance
# This page might be useful if you are just getting started with webmentions for the first time
# If you  need the setup page, set SHOW_SETUP to True
# I keep mine at False since as I run an instance that is only for me

import os

ROOT_DIRECTORY = os.path.dirname(os.path.abspath("__init__.py"))

RSS_DIRECTORY = "/home/capjamesg/webmention_receiver"

SQLALCHEMY_DATABASE_URI = 'sqlite:///webmentions.db'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# CALLBACK_URL = "https://webmention.jamesg.blog/callback"
# CLIENT_ID = "https://webmention.jamesg.blog/"
# TOKEN_ENDPOINT = "https://tokens.indieauth.com/token"
# ME = "https://jamesg.blog"

CALLBACK_URL = "http://localhost:5001/callback"
CLIENT_ID = "http://localhost:5001/"
TOKEN_ENDPOINT = "http://localhost:5000/token"
ME = "https://jamesg.blog/"

SHOW_SETUP = False