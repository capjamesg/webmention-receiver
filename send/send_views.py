from flask import request, jsonify, render_template, redirect, flash, Blueprint, current_app
from bs4 import BeautifulSoup
from ..config import ROOT_DIRECTORY
from ..auth.indieauth import requires_indieauth
from .send_function import *
import requests
import sqlite3

send = Blueprint('send', __name__, template_folder='templates')

@send.route("/discover")
def discover():
    target = request.args.get("target")

    if not target:
        return jsonify({"error": "No target specified."})

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

@send.route("/send", methods=["GET", "POST"])
@requires_indieauth
def send_webmention():
    if request.method == "POST":
        source = request.form.get("source")
        target = request.form.get("target")
        vouch = request.form.get("vouch")

        message, item = send_function(source, target)

        if item == None:
            flash(message)
            return redirect("/send")

        # Add webmentions to sent_webmentions table
        connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")

        if vouch:
            item.append(vouch)
        else:
            # "" means no vouch has been sent
            item.append("")

        # this means that the webmention has not yet been approved to show on my website
        # 0 = not approved
        # 1 = approved
        # using numbers because sqlite only supports integers as booleans
        item.append(0)

        with connection:
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO sent_webmentions (
                    source,
                    target,
                    sent_date,
                    status_code,
                    response,
                    webmention_endpoint,
                    location_header,
                    vouch,
                    approved_to_show
                ) VALUES (?, ?, ?, ?, ?, ?, ?)"""
            , tuple(item) )
            id = cursor.lastrowid
        
        return redirect("/sent/{}".format(id))

    return render_template("dashboard/send_webmention.html", title="Send a Webmention")

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
        raw_domain = current_app.config["ME"].split("/")[2]
        target_domain = target.split("/")[2]

        if not target_domain.endswith(raw_domain):
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
        r = requests.post(endpoint, 
            data={"source": source, "target": target},
            headers={"Content-Type": "application/x-www-form-urlencoded"})

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