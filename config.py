import os

ROOT_DIRECTORY = os.path.dirname(os.path.abspath("__init__.py"))

RSS_DIRECTORY = "/home/capjamesg/webmention_receiver"

SQLALCHEMY_DATABASE_URI = 'sqlite:///webmentions.db'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# CALLBACK_URL = "https://webmention.jamesg.blog/callback"
# CLIENT_ID = "https://webmention.jamesg.blog/"
# TOKEN_ENDPOINT = "https://tokens.indieauth.com/token"
# ME = "https://jamesg.blog"

CALLBACK_URL = "http://localhost:5000/callback"
CLIENT_ID = "http://localhost:5000/"
TOKEN_ENDPOINT = "https://tokens.indieauth.com/token"
ME = "https://jamesg.blog/"