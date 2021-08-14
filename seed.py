
from flask import Blueprint
import click
from werkzeug.security import generate_password_hash
from . import db
from .models import User
import sqlite3

seed_db = Blueprint('seed', __name__)

@seed_db.cli.command("create-user")
@click.argument("username")
def create_user(username):
    new_user = User(username=username, api_key="searchengine555James", password=generate_password_hash("searchengine555Jamesxyz2", method='sha256'))

    # add the new user to the database
    db.session.add(new_user)
    db.session.commit()
    print("created user {}".format(username))

@seed_db.cli.command("create-tables")
def create_tables(username):
    connection = sqlite3.connect("webmentions.db")

    with connection:
        cursor = connection.cursor()

        cursor.execute("CREATE TABLE user IF NOT EXISTS (id integer primary key autoincrement, username, password, api_key);")

        cursor.execute("CREATE TABLE webmentions IF NOT EXISTS (id integer primary key autoincrement, source, target, property, contents, author_name, author_phopto, author_url, content_html, received_date, status);")

        cursor.execute("CREATE TABLE sent_webmentions IF NOT EXISTS (id integer primary key autoincement, source, target, sent_date, status_code, response, webmention_endpoint);")

    print("created database tables")