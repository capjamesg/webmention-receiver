from flask import Flask, request, jsonify, render_template, redirect, flash, Blueprint
import requests
from werkzeug.security import check_password_hash
import datetime
from flask_login import login_required, current_user, login_user, logout_user
from bs4 import BeautifulSoup
import sqlite3
from .models import User
from .config import ROOT_DIRECTORY
from . import db
import math

main = Blueprint("main", __name__)

def change_to_json(database_result):
    columns = [column[0] for column in database_result.description]
    
    result = [dict(zip(columns, row)) for row in database_result]

    return result

@main.route("/", methods=["GET", "POST"])
def receiver():
    if current_user.is_authenticated:
        # Show dashboard if user is authenticated
        connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")

        page = request.args.get("page")

        if page and int(page) > 1:
            offset = (int(page) - 1) * 10
            page = int(page)
        else:
            offset = 0
            page = 1

        cursor = connection.cursor()

        with connection:
            count = cursor.execute("SELECT COUNT(*) FROM webmentions").fetchone()[0]
            webmentions = cursor.execute("SELECT source, target, received_date, contents, property, author_name FROM webmentions WHERE status = 'valid' ORDER BY received_date DESC LIMIT 10 OFFSET ?;", (offset,) ).fetchall()

        return render_template("home.html", webmentions=webmentions, sent=False, received_count=count, page=int(page), page_count=math.ceil(int(count) / 10), base_results_query="/")

    # If user GETs / and is not authenticated, code below runs

    if request.method == "GET":
        return jsonify({"message": "This is the James' Coffee Blog Webmention receiver."})

    # Process as www-form-encoded as per spec
    if request.content_type != "application/x-www-form-urlencoded":
        return jsonify({"message": "Content type must be x-www-url-formencoded."}), 400

    # Use force to get data (result of experimentation)
    
    source = request.form.get("source")
    target = request.form.get("target")

    if not (source.startswith("http://") or source.startswith("https://")) and (target.startswith("http://") or target.startswith("https://")):
        return jsonify({"message": "Source and target must use http:// or https:// protocols."}), 400

    if source == target:
        return jsonify({"message": "Source cannot be equal to target."}), 400

    # valid_targets must be a tuple to be compatible with startswith
    valid_targets = ("https://jamesg.blog", "http://jamesg.blog", "https://www.jamesg.blog", "http://www.jamesg.blog")
    if not target.startswith(valid_targets):
        return jsonify({"message": "Target must be a jamesg.blog resource."}), 400

    connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")

    with connection:
        cursor = connection.cursor()

        # Delete a webmention if it already exists so a new one can be added
        get_webmentions_for_url = cursor.execute("SELECT COUNT(source) FROM webmentions WHERE source = ? AND target = ?", (source, target, )).fetchone()

        if get_webmentions_for_url[0] > 0:
            cursor.execute("DELETE FROM webmentions WHERE source = ? AND target = ?", (source ,target,))
        else:
            cursor.execute("INSERT INTO webmentions (source, target, received_date, status, contents, property) VALUES (?, ?, ?, ?, ?, ?)", (source, target, str(datetime.datetime.now()), "validating", "", "", ))

        return jsonify({"message": "Created."}), 201

@main.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/home")

@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()

        # check if the user actually exists
        # take the user-supplied password, hash it, and compare it to the hashed password in the database
        if not user or not check_password_hash(user.password, password):
            flash("Please check your login details and try again.")
            return redirect("/login") # if the user doesn"t exist or password is wrong, reload the page

        # if the above check passes, then we know the user has the right credentials
        login_user(user, remember=True)

        return redirect("/home")
    else:
        if current_user.is_authenticated:
            return redirect("/home")

        return render_template("auth.html")

@main.route("/sent")
@login_required
def view_sent_webmentions_page():
    connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")

    page = request.args.get("page")

    if page and page.isnumeric() and int(page) > 1:
        offset = int(page) * 10
        page = int(page)
    else:
        offset = 0
        page = 1
    
    cursor = connection.cursor()
    with connection:
        count = cursor.execute("SELECT COUNT(*) FROM webmentions").fetchone()[0]
        webmentions = cursor.execute("SELECT source, target, sent_date, status_code, response, webmention_endpoint FROM sent_webmentions ORDER BY sent_date DESC LIMIT 10 OFFSET ?;", (offset,)).fetchall()

    return render_template("home.html", webmentions=webmentions, sent=True, page=int(page), page_count=int(int(count) / 10), base_results_query="/sent")

@main.route("/send", methods=["POST"])
@login_required
def send_webmention():
    source = request.form.get("source")
    target = request.form.get("target")

    # set up bs4
    r = requests.get(target)

    soup = BeautifulSoup(r.text, "lxml")

    a_webmention_tag = soup.find("a", {"rel": "webmention"})
    link_webmention_tag = soup.find("link", {"rel": "webmention"})

    if link_webmention_tag:
        endpoint = link_webmention_tag["href"]
    elif a_webmention_tag:
        endpoint = a_webmention_tag["href"]
    else:
        return jsonify({"message": "No endpoint could be found for this resource."}), 401

    if endpoint.startswith("/"):
        endpoint = "https://" + target.split("/")[2] + endpoint
    
    # make post request to endpoint with source and target as values
    r = requests.post(endpoint, data={"source": source, "target": target}, headers={"Content-Type": "application/x-www-form-urlencoded"})

    # Add webmentions to sent_webmentions table
    connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")

    with connection:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO sent_webmentions (source, target, sent_date, status_code, response, webmention_endpoint) VALUES (?, ?, ?, ?, ?, ?)", (source, target, str(datetime.datetime.now()), r.status_code, r.text, endpoint, ))

    if r.status_code != 200 and r.status_code != 201 and r.status_code != 202:
        return jsonify({"message": r.text}), r.status_code
    else:
        return jsonify({"message": r.text}), r.status_code

@main.route("/sent/json")
def retrieve_sent_webmentions_json():
    target = request.args.get("target")
    key = request.args.get("key")

    connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")
    with connection:
        cursor = connection.cursor()
        
        get_key = cursor.execute("SELECT api_key FROM user WHERE api_key = ?", (key, )).fetchone()

        if (get_key and len(get_key) == 0) or current_user.is_authenticated == False:
            return jsonify({"message": "You must be authenticated to retrieve all sent webmentions."}), 403

        if not target:
            get_webmentions = cursor.execute("SELECT * FROM sent_webmentions;")
        else:
            get_webmentions = cursor.execute("SELECT source, target, sent_date, status_code, response, webmention_endpoint FROM sent_webmentions WHERE target = ? ORDER BY sent_date DESC;", (target, )).fetchall()

        result = change_to_json(get_webmentions)

        return jsonify(result), 200

@main.route("/received")
def retrieve_webmentions():
    target = request.args.get("target")
    property = request.args.get("property")
    key = request.args.get("key")

    connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")

    cursor = connection.cursor()

    where_clause = ""

    if target:
        where_clause = "WHERE target = ?"
        attributes = (target, )
    
    if property:
        where_clause = "WHERE property = ?"
        attributes = (property, )

    if target and property:
        where_clause = "WHERE target = ? and property = ?"
        attributes = (target, property, )

    get_key = cursor.execute("SELECT api_key FROM user WHERE api_key = ?", (key, )).fetchone()
    
    if (get_key and len(get_key) == 0) or current_user.is_authenticated == False:
        return jsonify({"message": "You must be authenticated to retrieve all webmentions."}), 403

    if not target:
        get_webmentions = cursor.execute("SELECT * FROM webmentions;")
    else:
        get_webmentions = cursor.execute("SELECT source, target, contents, received_date, property, content_html, author_name, author_photo, author_url, status FROM webmentions {} ORDER BY received_date DESC;".format(where_clause), (attributes, )).fetchall()

    result = change_to_json(get_webmentions)

    return jsonify(result), 200