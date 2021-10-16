
from flask import Blueprint
import click
from werkzeug.security import generate_password_hash
from . import db
from .models import User
import sqlite3

seed_db = Blueprint('seed', __name__)

@seed_db.cli.command("create-tables")
def create_tables():
    connection = sqlite3.connect("webmentions.db")

    with connection:
        cursor = connection.cursor()

        cursor.execute("CREATE TABLE webmentions (id integer primary key autoincrement, source, target, property, contents, author_name, author_phopto, author_url, content_html, received_date, status);")

        cursor.execute("CREATE TABLE sent_webmentions (id integer primary key autoincement, source, target, sent_date, status_code, response, webmention_endpoint);")

        cursor.execute("CREATE TABLE webhooks (feed_url text, last_url_sent text);")

    print("created database tables")