from flask import request, jsonify, render_template, redirect, flash, Blueprint, current_app
from bs4 import BeautifulSoup
from ..config import ROOT_DIRECTORY
from ..auth.indieauth import requires_indieauth
from .send_function import *
import requests
import sqlite3

send = Blueprint('send', __name__, template_folder='templates')

@send.route("/endpoint/discover")
def discover_webmention_endpoint():
    target = request.args.get("target")

    endpoint = discover_webmention_endpoint(target)

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
        
        return redirect(f"/sent/{id}")

    return render_template("dashboard/send_webmention.html", title="Send a Webmention")

@send.route("/send/open", methods=["POST"])
def send_webmention_anyone():
    if request.method == "POST":
        source = request.form.get("source")
        target = request.form.get("target")

        message = send_webmention(source, target)
        
        return render_template("send_open.html", message=message)