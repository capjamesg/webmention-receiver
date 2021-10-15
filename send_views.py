from flask import request, jsonify, render_template, redirect, flash, Blueprint, send_from_directory, abort, session, current_app
import requests
import datetime
from bs4 import BeautifulSoup
import sqlite3
from .config import ROOT_DIRECTORY, RSS_DIRECTORY
from .indieauth import requires_indieauth
import math
import json

send = Blueprint('send', __name__, template_folder='templates')

@send.route("/discover", methods=["POST"])
def discover():
    target = request.args.get("target")

    r = requests.get(target, allow_redirects=True)

    soup = BeautifulSoup(r.text, "lxml")
    
    link_header = r.headers.get("Link")

    endpoint = None

    if link_header:
        parsed_links = requests.utils.parse_header_links(link_header.rstrip('>').replace('>,<', ',<'))

        for link in parsed_links:
            if "webmention" in link["rel"]:
                endpoint = link["url"]
                break

    if endpoint == None:
        for item in soup():
            if item.name == "a" and item.get("rel") and item["rel"][0] == "webmention":
                endpoint = item.get("href")
                break
            elif item.name == "link" and item.get("rel") and item["rel"][0] == "webmention":
                endpoint = item.get("href")
                break

    if endpoint == None:
        message = "No endpoint could be found for this resource."
        return jsonify({"success": False, "message": message}), 400

    if endpoint == "0.0.0.0" or endpoint == "127.0.0.1" or endpoint == "localhost":
        message = "This resource is not supported."
        return jsonify({"success": False, "message": message}), 400

    if endpoint == "":
        endpoint = target

    if not endpoint.startswith("https://") and not endpoint.startswith("http://") and not endpoint.startswith("/"):
        if r.history:
            endpoint = "/".join(r.url.split("/")[:-1]) + "/" + endpoint
        else:
            endpoint = "/".join(target.split("/")[:-1]) + "/" + endpoint

    if endpoint.startswith("/"):
        if r.history:
            endpoint = "https://" + r.url.split("/")[2] + endpoint
        else:
            endpoint = "https://" + target.split("/")[2] + endpoint

    if endpoint == None:
        message = "No endpoint could be found for this resource."
        return jsonify({"success": False, "message": message}), 400
    
    return jsonify({"success": True, "endpoint": endpoint}), 200

def send_function(source, target):
    if not target.startswith("https://"):
        flash("Target must use https:// protocol.")
        return redirect("/send")

    # set up bs4
    r = requests.get(target, allow_redirects=True)

    soup = BeautifulSoup(r.text, "lxml")
    
    link_header = r.headers.get("Link")

    endpoint = None

    if link_header:
        parsed_links = requests.utils.parse_header_links(link_header.rstrip('>').replace('>,<', ',<'))

        for link in parsed_links:
            if "webmention" in link["rel"]:
                endpoint = link["url"]
                break

    if endpoint == None:
        for item in soup():
            if item.name == "a" and item.get("rel") and item["rel"][0] == "webmention":
                endpoint = item.get("href")
                break
            elif item.name == "link" and item.get("rel") and item["rel"][0] == "webmention":
                endpoint = item.get("href")
                break

    if endpoint == None:
        flash("No endpoint could be found for this resource.")
        return redirect("/send")

    if endpoint == "0.0.0.0" or endpoint == "127.0.0.1" or endpoint == "localhost":
        flash("This resource is not supported.")
        return redirect("/send")

    if endpoint == "":
        endpoint = target

    if not endpoint.startswith("https://") and not endpoint.startswith("http://") and not endpoint.startswith("/"):
        if r.history:
            endpoint = "/".join(r.url.split("/")[:-1]) + "/" + endpoint
        else:
            endpoint = "/".join(target.split("/")[:-1]) + "/" + endpoint

    if endpoint.startswith("/"):
        if r.history:
            endpoint = "https://" + r.url.split("/")[2] + endpoint
        else:
            endpoint = "https://" + target.split("/")[2] + endpoint
    
    # make post request to endpoint with source and target as values
    r = requests.post(endpoint, data={"source": source, "target": target}, headers={"Content-Type": "application/x-www-form-urlencoded"})

    if r.headers and r.headers.get("Location"):
        location_header = r.headers.get("Location")
    else:
        location_header = ""

    try:
        message = str(r.json())
    except:
        message = r.text

    # Add webmentions to sent_webmentions table
    connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")

    with connection:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO sent_webmentions (source, target, sent_date, status_code, response, webmention_endpoint, location_header) VALUES (?, ?, ?, ?, ?, ?, ?)", (source, target, str(datetime.datetime.now()), r.status_code, message, endpoint, location_header, ))
        id = cursor.lastrowid
        cursor.execute("UPDATE sent_webmentions SET response = ? WHERE id = ?", (message, id, ))

    return id

@send.route("/send", methods=["GET", "POST"])
@requires_indieauth
def send_webmention():
    if request.method == "POST":
        source = request.form.get("source")
        target = request.form.get("target")

        id = send_function(source, target)
        
        return redirect("/sent/{}".format(id))

    return render_template("send_webmention.html", title="Send a Webmention")

@send.route("/send/open", methods=["POST"])
def send_webmention_anyone():
    if request.method == "POST":
        source = request.form.get("source")
        target = request.form.get("target")

        if not source and not target:
            message = {
                "title": "Please enter a source and target.",
                "description": "Please enter a source and target.",
                "url": target
            }

            return render_template("send_open.html", message=message)


        if not target.startswith("https://"):
            message = {
                "title": "Error: Target must use https:// protocol.",
                "description": "Target must use https:// protocol.",
                "url": target
            }

            return render_template("send_open.html", message=message)


        # if domain is not approved, don't allow access
        raw_domain = current_app.config["ME"].replace("http://", "").replace("https://", "")
        if not target.startswith("http://" + raw_domain) or target.startswith("http://" + raw_domain):
            message = {
                "title": "Error: Target must be a {} post.".format(current_app.config["ME"]),
                "description": "Target must be a {} post.".format(current_app.config["ME"]),
                "url": target
            }

            return render_template("send_open.html", message=message)

        # set up bs4
        r = requests.get(target, allow_redirects=True)

        soup = BeautifulSoup(r.text, "lxml")
        
        link_header = r.headers.get("Link")

        endpoint = None

        if link_header:
            parsed_links = requests.utils.parse_header_links(link_header.rstrip('>').replace('>,<', ',<'))

            for link in parsed_links:
                if "webmention" in link["rel"]:
                    endpoint = link["url"]
                    break

        if endpoint == None:
            for item in soup():
                if item.name == "a" and item.get("rel") and item["rel"][0] == "webmention":
                    endpoint = item.get("href")
                    break
                elif item.name == "link" and item.get("rel") and item["rel"][0] == "webmention":
                    endpoint = item.get("href")
                    break

        if endpoint == "0.0.0.0" or endpoint == "127.0.0.1" or endpoint == "localhost":
            message = {
                "title": "Error:" + "Your endpoint is not supported.",
                "description": "Your endpoint is not supported.",
                "url": target
            }

            return render_template("send_open.html", message=message)

        if endpoint == None:
            message = {
                "title": "Error:" + "No endpoint could be found for this resource.",
                "description": "No endpoint could be found for this resource.",
                "url": target
            }

            return render_template("send_open.html", message=message)


        if endpoint == "":
            endpoint = target

        if not endpoint.startswith("https://") and not endpoint.startswith("http://") and not endpoint.startswith("/"):
            if r.history:
                endpoint = "/".join(r.url.split("/")[:-1]) + "/" + endpoint
            else:
                endpoint = "/".join(target.split("/")[:-1]) + "/" + endpoint

        if endpoint.startswith("/"):
            if r.history:
                endpoint = "https://" + r.url.split("/")[2] + endpoint
            else:
                endpoint = "https://" + target.split("/")[2] + endpoint
        
        # make post request to endpoint with source and target as values
        r = requests.post(endpoint, data={"source": source, "target": target}, headers={"Content-Type": "application/x-www-form-urlencoded"})

        message = str(r.json()["message"])

        if r.status_code == 200 or r.status_code == 201 or r.status_code == 202:
            message = {
                "title": message,
                "description": message,
                "url": target
            }
        else:
            message = {
                "title": "Error: " + message,
                "description": "Error: " + message,
                "url": target
            }

        return render_template("send_open.html", message=message)