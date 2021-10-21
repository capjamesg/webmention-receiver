from flask import request, jsonify, render_template, redirect, flash, Blueprint, send_from_directory, abort, session, current_app
from .config import ROOT_DIRECTORY, RSS_DIRECTORY, SHOW_SETUP
from .indieauth import requires_indieauth
from bs4 import BeautifulSoup
import requests
import datetime
import sqlite3
import mf2py
import math
import json

main = Blueprint("main", __name__, static_folder="static", static_url_path="")

def change_to_json(database_result):
    columns = [column[0] for column in database_result.description]
    
    result = [dict(zip(columns, row)) for row in database_result]

    return result

@main.route("/")
def index():
    # redirect logged in users to the dashboard
    if session.get("me"):
        return redirect("/home")

    return render_template("index.html", title="{} Webmention Receiver Home".format(current_app.config["ME"].strip().replace("https://", "").replace("http://", "")))

@main.route("/home")
def homepage():
    # Only show dashboard if user is authenticated
    if not session.get("me"):
        return redirect("/login")

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

@main.route("/endpoint", methods=["POST"])
def receiver():
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
                if r.status_code == 200:
                    text = r.text
                else:
                    text = "Error: {}, {}".format(r.status_code, r.text)

                cursor.execute("UPDATE sent_webmentions SET response = ?, location_header = ? WHERE source = ? AND target = ?", (text, "", c[1], c[2], ))

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
                text = r.text
            else:
                text = "Error: {}, {}".format(r.status_code, r.text)

            cursor.execute("UPDATE sent_webmentions SET response = ? AND location_header = ? WHERE source = ? AND target = ?", (text, "", webmention[1], webmention[2], ))

        webmention = cursor.execute("SELECT * FROM sent_webmentions WHERE id = ?", (wm,)).fetchone()

        parsed_response = str(webmention[5]).replace("'", "\"")

        try:
            final_parsed_response = json.loads(parsed_response)
        except:
            final_parsed_response = parsed_response
        
        if webmention:
            return render_template("webmention.html", webmention=webmention, title="Webmention to {} Details".format(webmention[1]), \
                response=final_parsed_response)
        else:
            return abort(404)

@main.route("/sent/json")
def retrieve_sent_webmentions_json():
    target = request.args.get("target")
    status = request.args.get("status")
    key = request.args.get("key")

    connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")
    with connection:
        cursor = connection.cursor()
        
        get_key = cursor.execute("SELECT api_key FROM user WHERE api_key = ?", (key, )).fetchone()

        if ((get_key and len(get_key) == 0) and not session.get("me")) or not get_key:
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

    if not get_key and session.get("me") and where_clause == "":
        return jsonify({"message": "You must be authenticated to retrieve all webmentions."}), 403

    if not target:
        get_webmentions = cursor.execute("SELECT * FROM webmentions;")
        result = change_to_json(get_webmentions)

        count = cursor.execute("SELECT COUNT(source), property FROM webmentions GROUP BY property;").fetchall()
    else:
        get_webmentions = cursor.execute("SELECT * FROM webmentions {} ORDER BY received_date ASC;".format(where_clause), attributes, )
        result = change_to_json(get_webmentions)

        count = cursor.execute("SELECT COUNT(source), property FROM webmentions {} GROUP BY property;".format(where_clause), attributes, ).fetchall()

    aggregate_count = 0

    parsed_counts = {}

    for item in count:
        aggregate_count += item[0]
        parsed_counts[item[1]] = item[0]
    
    response = jsonify({
        "count": aggregate_count,
        "count_by_property": parsed_counts,
        "webmentions": result
    })

    response.headers['Access-Control-Allow-Origin'] = '*'

    return response, 200

@main.route("/webhook", methods=["GET", "POST"])
def webhook_check():
    connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")
    key = request.args.get("key")
    
    with connection:
        cursor = connection.cursor()

        get_key = cursor.execute("SELECT api_key FROM user WHERE api_key = ?", (key, )).fetchone()
        
        if (get_key and len(get_key) == 0) or not get_key:
            return jsonify({"message": "You must be authenticated to access this resource."}), 403

        feed_url = request.args.get('url')

        if not feed_url:
            return jsonify({"message": "You must provide a url to check."}), 400

        check_if_queued = cursor.execute("SELECT * FROM pending_webmentions WHERE to_check = ?", (feed_url, )).fetchone()

        if check_if_queued:
            return jsonify({"message": "This url is already queued to be checked."}), 400

        cursor.execute("INSERT INTO pending_webmentions (to_check) VALUES (?);", (feed_url, ))

    return jsonify({"message": "URLs queued for processing."}), 202

@main.route("/stats")
@requires_indieauth
def stats_page():
    connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")
    with connection:
        cursor = connection.cursor()

        get_webmentions = cursor.execute("SELECT count(*) FROM webmentions;").fetchone()[0]

        get_sent_webmentions = cursor.execute("SELECT count(*) FROM sent_webmentions;").fetchone()[0]

        received_types = cursor.execute("SELECT property, count(*) FROM webmentions WHERE status = 'valid' GROUP BY property;").fetchall()

        pending_webmention_count = cursor.execute("SELECT count(*) FROM webmentions WHERE status = 'validating';").fetchone()[0]

        return render_template("stats.html", received_count=get_webmentions, sent_count=get_sent_webmentions, received_types=received_types, pending_webmention_count=pending_webmention_count)

@main.route("/rss")
def rss():
    key = request.args.get("key")

    connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")

    cursor = connection.cursor()

    get_key = cursor.execute("SELECT api_key FROM user WHERE api_key = ?", (key, )).fetchone()
    
    if ((get_key and len(get_key) == 0) and not session.get("me")) or not get_key:
        return jsonify({"message": "You must be authenticated to retrieve all webmentions."}), 403
    
    return send_from_directory(RSS_DIRECTORY + "/static/", "webmentions.xml")

@main.route("/static/images/<path:filename>")
def send_images(filename):
    return send_from_directory(ROOT_DIRECTORY + "/webmention_receiver/static/images/", filename)

@main.route("/robots.txt")
def robots():
    return send_from_directory(main.static_folder, "robots.txt")

@main.route("/favicon.ico")
def favicon():
    return send_from_directory(main.static_folder, "favicon.ico")

@main.route("/setup")
def setup_page():
    if SHOW_SETUP == True:
        return render_template("setup.html", title="Setup Your Webmention Endpoint")
    else:
        abort(404)