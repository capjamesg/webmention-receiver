from flask import request, jsonify, render_template, redirect, flash, Blueprint, send_from_directory, abort, session, current_app
import requests
import datetime
from bs4 import BeautifulSoup
import sqlite3
from .config import ROOT_DIRECTORY, RSS_DIRECTORY
from .indieauth import requires_indieauth
import math
import json

main = Blueprint("main", __name__)

def change_to_json(database_result):
    columns = [column[0] for column in database_result.description]
    
    result = [dict(zip(columns, row)) for row in database_result]

    return result

@main.route("/", methods=["GET", "POST"])
@requires_indieauth
def receiver():
    if session.get("me") and request.method == "GET":
        # Show dashboard if user is authenticated
        connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")

        page = request.args.get("page")

        if page and int(page) > 1:
            offset = (int(page) - 1) * 10
            page = int(page)
        else:
            offset = 0
            page = 1

        sort_param = request.args.get("sort")

        if sort_param == "oldest":
            sort_order = "ASC"
        else:
            sort_order = "DESC"

        cursor = connection.cursor()

        with connection:
            count = cursor.execute("SELECT COUNT(*) FROM webmentions").fetchone()[0]
            webmentions = cursor.execute("SELECT source, target, received_date, contents, property, author_name FROM webmentions WHERE status = 'valid' ORDER BY received_date {} LIMIT 10 OFFSET ?;".format(sort_order), (offset,) ).fetchall()

        return render_template("feed.html", webmentions=webmentions, sent=False, received_count=count, page=int(page), page_count=math.ceil(int(count) / 10), base_results_query="/", title="Received Webmentions", sort=sort_param)

    # If user GETs / and is not authenticated, code below runs

    if request.method == "GET":
        return render_template("index.html", title="{} Webmention Receiver Home".format(current_app.config["ME"].strip().replace("https://", "").replace("http://", "")))

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

    # Make sure source and target are not identical when a trailing slash is removed from both
    if source.strip("/") == target.strip("/"):
        return jsonify({"message": "Source cannot be equal to target."}), 400

    # valid_targets must be a tuple to be compatible with startswith

    raw_domain = current_app.config["ME"].replace("http://", "").replace("https://", "")

    valid_targets = ("https://{}".format(raw_domain), "http://{}".format(raw_domain))
    if not target.startswith(valid_targets):
        return jsonify({"message": "Target must be a {} resource.".format(raw_domain)}), 400

    connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")

    with connection:
        cursor = connection.cursor()

        # Rreprocess webmentions from the same source
        # Ensures all webmentions from source X are updated when a new webmention is sent from that source

        already_sent_from_source = cursor.execute("SELECT source, target FROM webmentions WHERE source = ?", (target, )).fetchall()

        for a in already_sent_from_source:
            cursor.execute("INSERT INTO webmentions (source, target, received_date, status, contents, property) VALUES (?, ?, ?, ?, ?, ?)", (a[0], a[1], str(datetime.datetime.now()), "validating", "", "", ))

        cursor.execute("DELETE FROM webmentions WHERE source = ? and target = ?", (source, target, ))
        
        cursor.execute("INSERT INTO webmentions (source, target, received_date, status, contents, property) VALUES (?, ?, ?, ?, ?, ?)", (source, target, str(datetime.datetime.now()), "validating", "", "", ))

        return jsonify({"message": "Accepted."}), 202

@main.route("/callback")
def indieauth_callback():
    code = request.args.get("code")

    data = {
        "code": code,
        "redirect_uri": current_app.config["CALLBACK_URL"],
        "client_id": current_app.config["CLIENT_ID"]
    }

    headers = {
        "Accept": "application/json"
    }

    r = requests.post("https://tokens.indieauth.com/token", data=data, headers=headers)
    
    if r.status_code != 200:
        flash("Your authentication failed. Please try again.")
        return redirect("/login")

    if r.json().get("me").strip("/") != current_app.config["ME"].strip("/"):
        flash("Your domain is not allowed to access this website.")
        return redirect("/login")

    session["me"] = r.json().get("me")
    session["access_token"] = r.json().get("access_token")

    return redirect("/")

@main.route("/delete", methods=["POST"])
@requires_indieauth
def delete_webmention():
    if request.method == "POST":
        target = request.form.get("target")
        source = request.form.get("source")

        if not target and not source:
            flash("Please provide a target and a source.")
            return redirect("/")
        
        connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")

        with connection:
            cursor = connection.cursor()

            cursor.execute("DELETE FROM webmentions WHERE target = ? AND source = ?", (target, source))

        flash("Webmention from {} has been deleted.".format(target))
        return redirect("/")
    else:
        return abort(405)

@main.route("/logout")
@requires_indieauth
def logout():
    session.pop("me")
    session.pop("access_token")

    return redirect("/home")

@main.route("/login", methods=["GET", "POST"])
def login():
    return render_template("auth.html", title="Webmention Dashboard Login")

@main.route("/sent")
@requires_indieauth
def view_sent_webmentions_page():
    connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")

    page = request.args.get("page")

    if page and page.isnumeric() and int(page) > 1:
        offset = int(page) * 10
        page = int(page)
    else:
        offset = 0
        page = 1

    sort_param = request.args.get("sort")

    if sort_param == "oldest":
        sort_order = "ASC"
    else:
        sort_order = "DESC"

    with connection:
        cursor = connection.cursor()

        count = cursor.execute("SELECT COUNT(id) FROM sent_webmentions").fetchone()[0]
        to_process = cursor.execute("SELECT id, source, target, sent_date, status_code, response, webmention_endpoint, location_header FROM sent_webmentions ORDER BY sent_date {} LIMIT 10 OFFSET ?;".format(sort_order), (offset,)).fetchall()

        for c in to_process:
            if c[7] and c[7] != "" and c[7] != None:
                r = requests.get(c[7])
                cursor.execute("UPDATE sent_webmentions SET response = ?, location_header = ? WHERE source = ? AND target = ?", (str(r.json()), "", c[1], c[2], ))

    with connection:
        cursor = connection.cursor()
        
        webmentions = cursor.execute("SELECT id, source, target, sent_date, status_code, response, webmention_endpoint, location_header FROM sent_webmentions ORDER BY sent_date {} LIMIT 10 OFFSET ?;".format(sort_order), (offset,)).fetchall()

    return render_template("sent.html", webmentions=webmentions, sent=True, page=int(page), page_count=int(int(count) / 10), base_results_query="/sent", title="Your Sent Webmentions", sort=sort_param, count=count)

@main.route("/sent/<wm>")
@requires_indieauth
def view_sent_webmention(wm):
    connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")

    with connection:
        cursor = connection.cursor()
        webmention = cursor.execute("SELECT * FROM sent_webmentions WHERE id = ?", (wm,)).fetchone()

        if not webmention:
            abort(404)

        if webmention[7] and webmention[7] != "":
            r = requests.get(webmention[7])

            if r.status_code == 200:
                cursor.execute("UPDATE sent_webmentions SET response = ? AND location_header = ? WHERE source = ? AND target = ?", (r.text, "", webmention[1], webmention[2], ))

        webmention = cursor.execute("SELECT * FROM sent_webmentions WHERE id = ?", (wm,)).fetchone()

        parsed_response = str(webmention[5].replace("'", "\""))

        final_parsed_response = json.loads(parsed_response)
        
        if webmention:
            return render_template("webmention.html", webmention=webmention, title="Webmention to {} Details".format(webmention[1]), \
                response=json.loads(final_parsed_response))
        else:
            return abort(404)

@main.route("/send", methods=["GET", "POST"])
@requires_indieauth
def send_webmention():
    if request.method == "POST":
        source = request.form.get("source")
        target = request.form.get("target")

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

        # Add webmentions to sent_webmentions table
        connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")

        if r.headers and r.headers.get("Location"):
            location_header = r.headers.get("Location")
        else:
            location_header = ""

        try:
            message = str(r.json())
        except:
            message = r.text

        try:
            with connection:
                cursor = connection.cursor()
                cursor.execute("INSERT INTO sent_webmentions (source, target, sent_date, status_code, response, webmention_endpoint, location_header) VALUES (?, ?, ?, ?, ?, ?, ?)", (source, target, str(datetime.datetime.now()), r.status_code, message, endpoint, location_header, ))
                id = cursor.lastrowid
                cursor.execute("UPDATE sent_webmentions SET response = ? WHERE id = ?", (message, id, ))

            return redirect("/sent/{}".format(id))
        except:
            flash("There was an error processing your webmention.")
            return render_template("send_webmention.html", title="Send a Webmention")

    return render_template("send_webmention.html", title="Send a Webmention")

@main.route("/send/open", methods=["POST"])
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

@main.route("/sent/json")
def retrieve_sent_webmentions_json():
    target = request.args.get("target")
    status = request.args.get("status")
    key = request.args.get("key")

    connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")
    with connection:
        cursor = connection.cursor()
        
        get_key = cursor.execute("SELECT api_key FROM user WHERE api_key = ?", (key, )).fetchone()

        if (get_key and len(get_key) == 0) and not session.get("me"):
            return jsonify({"message": "You must be authenticated to retrieve all sent webmentions."}), 403

        if status == "valid":
            status = "AND status = 'valid'"
        elif status == "invalid":
            status = "AND status = 'invalid'"
        else:
            status = ""

        if not target:
            get_webmentions = cursor.execute("SELECT * FROM sent_webmentions;")
        else:
            get_webmentions = cursor.execute("SELECT source, target, sent_date, status_code, response, webmention_endpoint FROM sent_webmentions WHERE target = ? {} ORDER BY sent_date ASC;".format(status), (target, )).fetchall()

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
        where_clause = "WHERE target = ? AND status = 'valid'"
        attributes = (target, )
    
    if property:
        where_clause = "WHERE property = ? AND status = 'valid'"
        attributes = (property, )

    if target and property:
        where_clause = "WHERE target = ? and property = ? AND status = 'valid'"
        attributes = (target, property, )

    get_key = cursor.execute("SELECT api_key FROM user WHERE api_key = ?", (key, )).fetchone()

    if not target:
        get_webmentions = cursor.execute("SELECT * FROM webmentions;")
    else:
        get_webmentions = cursor.execute("SELECT * FROM webmentions {} ORDER BY received_date ASC;".format(where_clause), attributes, )
    
    if not get_key and session.get("me") and where_clause == "":
        return jsonify({"message": "You must be authenticated to retrieve all webmentions."}), 403

    result = change_to_json(get_webmentions)

    # send Access-Control-Allow-Origin header
    response = jsonify(result)
    response.headers['Access-Control-Allow-Origin'] = '*'

    return response, 200

@main.route("/stats")
@requires_indieauth
def stats_page():
    connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")
    with connection:
        cursor = connection.cursor()

        get_webmentions = cursor.execute("SELECT count(*) FROM webmentions;").fetchone()[0]

        get_sent_webmentions = cursor.execute("SELECT count(*) FROM sent_webmentions;").fetchone()[0]

        received_types = cursor.execute("SELECT property, count(*) FROM webmentions GROUP BY property;").fetchall()

        return render_template("stats.html", received_count=get_webmentions, sent_count=get_sent_webmentions, received_types=received_types)

@main.route("/rss")
def rss():
    key = request.args.get("key")

    connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")

    cursor = connection.cursor()

    get_key = cursor.execute("SELECT api_key FROM user WHERE api_key = ?", (key, )).fetchone()
    
    if (get_key and len(get_key) == 0) and not session.get("me"):
        return jsonify({"message": "You must be authenticated to retrieve all webmentions."}), 403
    
    return send_from_directory(RSS_DIRECTORY + "/static/", "webmentions.xml")

@main.route("/static/images/<path:filename>")
def send_images(filename):
    return send_from_directory(ROOT_DIRECTORY + "/webmention_receiver/static/images/", filename)