from flask import request, jsonify, render_template, redirect, flash, Blueprint, send_from_directory, abort, session, current_app
import requests
import datetime
from bs4 import BeautifulSoup
import sqlite3
from .config import ROOT_DIRECTORY, RSS_DIRECTORY
from .indieauth import requires_indieauth
import math
import json

auth = Blueprint('auth', __name__)

@auth.route("/callback")
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

@auth.route("/logout")
@requires_indieauth
def logout():
    session.pop("me")
    session.pop("access_token")

    return redirect("/home")

@auth.route("/login", methods=["GET", "POST"])
def login():
    return render_template("auth.html", title="Webmention Dashboard Login")