from flask import request, render_template, redirect, flash, Blueprint, session, current_app
from .config import AUTH_ENDPOINT, TOKEN_ENDPOINT, CLIENT_ID, CALLBACK_URL
from .indieauth import requires_indieauth
from bs4 import BeautifulSoup
import requests
import hashlib
import base64
import string
import random

auth = Blueprint('auth', __name__)

@auth.route("/callback")
def indieauth_callback():
    code = request.args.get("code")
    state = request.args.get("state")

    if state != session.get("state"):
        flash("Your authentication failed. Please try again.")
        return redirect("/")

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

    r = requests.post(session.get("token_endpoint"), data=data, headers=headers)
    
    if r.status_code != 200:
        flash("There was an error with your token endpoint server.")
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

@auth.route("/discover", methods=["POST"])
def discover_auth_endpoint():
    domain = request.form.get("me")

    r = requests.get(domain)

    soup = BeautifulSoup(r.text, "html.parser")

    token_endpoint = soup.find("link", rel="token_endpoint")

    if token_endpoint is None:
        flash("An IndieAuth token ndpoint could not be found on your website.")
        return redirect("/login")

    if not token_endpoint.get("href").startswith("https://") and not token_endpoint.get("href").startswith("http://"):
        flash("Your IndieAuth token endpoint published on your site must be a full HTTP URL.")
        return redirect("/login")

    auth_endpoint = token_endpoint["href"]

    random_code = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(30))

    session["code_verifier"] = random_code
    session["token_endpoint"] = token_endpoint["href"]

    sha256_code = hashlib.sha256(random_code.encode('utf-8')).hexdigest()

    code_challenge = base64.b64encode(sha256_code.encode('utf-8')).decode('utf-8')

    state = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))

    session["state"] = state

    return redirect(auth_endpoint + "?client_id=" + CLIENT_ID + "&redirect_uri=" + CALLBACK_URL + "&scope=profile&response_type=code&code_challenge=" + code_challenge + "&code_challenge_method=S256&state=" + state)

@auth.route("/login", methods=["GET", "POST"])
def login():
    return render_template("auth.html", title="Webmention Dashboard Login")