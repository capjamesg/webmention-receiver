from flask import request, render_template, redirect, flash, Blueprint, session, current_app
from .config import TOKEN_ENDPOINT, CLIENT_ID, CALLBACK_URL
from .indieauth import requires_indieauth
import requests
import hashlib
import base64
import string
import random

auth = Blueprint('auth', __name__)

@auth.route("/callback")
def indieauth_callback():
    code = request.args.get("code")

    data = {
        "code": code,
        "redirect_uri": CALLBACK_URL,
        "client_id": CLIENT_ID,
        "grant_type": "authorization_code",
        "code_verifier": session["code_verifier"]
    }

    headers = {
        "Accept": "application/json"
    }

    r = requests.post(TOKEN_ENDPOINT, data=data, headers=headers)
    
    if r.status_code != 200:
        flash("Your authentication failed. Please try again.")
        return redirect("/login")

    # remove code verifier from session because the authentication flow has finished
    session.pop("code_verifier")

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
    random_code = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(30))

    session["code_verifier"] = random_code

    sha256_code = hashlib.sha256(random_code.encode('utf-8')).hexdigest()

    code_challenge = base64.b64encode(sha256_code.encode('utf-8')).decode('utf-8')

    state = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))

    return render_template("auth.html", title="Webmention Dashboard Login", code_challenge=code_challenge, state=state)