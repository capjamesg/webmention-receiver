from flask import Flask, request, jsonify, render_template, redirect, make_response
import requests
import mf2py
import json
import datetime
import mf2util
from bs4 import BeautifulSoup
import sqlite3
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
import os
import secrets

load_dotenv()

app = Flask(__name__)

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# TODO: Implement async task loading, add support for updating existing webmentions
# Add support for pingbacks

@app.route("/", methods=["GET", "POST"])
def receiver():
    if request.method == "GET":
        return jsonify({"message": "This is the James' Coffee Blog Webmention receiver."})
    else:
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

        connection = sqlite3.connect("webmentions.db")

        with connection:
            cursor = connection.cursor()

            # Delete a webmention if it already exists so a new one can be added
            get_webmentions_for_url = cursor.execute("SELECT COUNT(source) FROM webmentions WHERE source = ? AND target = ?", (source, target, )).fetchone()

            if get_webmentions_for_url[0] > 0:
                cursor.execute("DELETE FROM webmentions WHERE source = ? AND target = ?", (source ,target,))
            else:
                cursor.execute("INSERT INTO webmentions (source, target, received_date, status, contents, property) VALUES (?, ?, ?, ?, ?, ?)", (source, target, str(datetime.datetime.now()), "validating", "", "", ))

            return jsonify({"message": "Created."}), 201

@app.route("/home")
def view_webmentions_page():
    connection = sqlite3.connect("webmentions.db")

    cursor = connection.cursor()
    with connection:
        webmentions = cursor.execute("SELECT source, target, received_date, contents, property, author_name FROM webmentions WHERE status = 'valid'").fetchall()

    key = request.args.get("key")

    if key == os.environ.get("api-key"):
        return render_template("home.html", webmentions=webmentions, sent=False, key=key)
    else:
        return jsonify({"message": "You must be authenticated to view this resource."}), 401

@app.route("/auth")
def view_auth_page():
    token = secrets.token_hex(16)

    response = make_response(render_template("auth.html", token=token))

    response.set_cookie("token", token)

    return response

@app.route("/auth/handle")
def handle_authentication_response_from_indielogin():
    check_token = request.cookies.get("token")

    if check_token != request.form.get("token"):
        return redirect("/home", code=302, message="Your authentication token is invalid. Please try signing in again.")

    r = requests.post("https://indielogin.com/auth", headers={"Content-Type": "application/x-www-form-urlencoded"}, data={"code":request.form.get("code"), "redirect_uri": "https://webmention.jamesg.blog/auth/handle", "client_id": os.environ.get("client-id"), "client_id": "https://webmention.jamesg.blog"})

    if r.status_code != 200:
        return redirect("/auth", code=302, message="There was an error authenticating with the IndieLogin service. Please try again.")

    return redirect("/home", code=302, message="You have successfully authenticated with the IndieLogin service.")

@app.route("/sent")
def view_sent_webmentions_page():
    connection = sqlite3.connect("webmentions.db")

    cursor = connection.cursor()
    with connection:
        webmentions = cursor.execute("SELECT source, target, sent_date, status_code, response, webmention_endpoint FROM sent_webmentions").fetchall()

    key = request.args.get("key")

    if key == os.environ.get("api-key"):
        return render_template("home.html", webmentions=webmentions, sent=True, key=key)
    else:
        return jsonify({"message": "You must be authenticated to view this resource."}), 401

@app.route("/send", methods=["POST"])
def send_webmention():
    source = request.form.get("source")
    target = request.form.get("target")

    # set up bs4
    r = requests.get(target)

    soup = BeautifulSoup(r.text, "lxml")

    a_webmention_tag = soup.find("a", {"rel": "webmention"})
    link_webmention_tag = soup.find("link", {"rel": "webmention"})

    print(a_webmention_tag)
    print(link_webmention_tag)

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
    connection = sqlite3.connect("webmentions.db")

    with connection:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO sent_webmentions (source, target, sent_date, status_code, response, webmention_endpoint) VALUES (?, ?, ?, ?, ?, ?)", (source, target, str(datetime.datetime.now()), r.status_code, r.text, endpoint, ))

    if r.status_code != 200 and r.status_code != 201 and r.status_code != 202:
        return jsonify({"message": r.text}), r.status_code
    else:
        return jsonify({"message": r.text}), r.status_code

@app.route("/retrieve")
def retrieve_webmentions():
    target = request.args.get("target")
    property = request.args.get("property")
    key = request.args.get("key")

    connection = sqlite3.connect("webmentions.db")

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

    if where_clause == "":
        if key == os.environ.get("api-key"):
            get_webmentions = cursor.execute("SELECT * FROM webmentions;")
        else:
            return jsonify({"message": "You must be authenticated to retrieve all webmentions."}), 400
    else:
        get_webmentions = cursor.execute("SELECT source, target, contents, received_date, property, content_html, author_name, author_photo, author_url, status FROM webmentions {};".format(where_clause), attributes).fetchall()

    webmentions = []

    for source, target, content, received_date, property, content_html, author_name, author_photo, author_url, status in get_webmentions:
        response = {}

        if source:
            response["source"] = source
        if target:
            response["target"] = target
        if content:
            response["content"] = content
        if received_date:
            response["received_date"] = received_date
        if property:
            response["property"] = property
        if content_html:
            response["content_html"] = content_html
        if author_name:
            response["author"] = {"name": "", "photo": "", "url": ""}
            response["author"]["name"] = author_name
            response["author"]["photo"] = author_photo
            response["author"]["url"] = author_url
        if status:
            response["status"] = status

        webmentions.append(response)

    return jsonify(webmentions), 200