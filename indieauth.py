# -*- coding: utf-8 -*-
"""
    Flask-IndieAuth
    ==============
    This extension adds the ability to authorize requests to your Flask
    endpoints via [IndieAuth](https://indieweb.org/IndieAuth), using
    current_app.config['TOKEN_ENDPOINT'] as the token server.
    This is useful for developers of Micropub (https://www.w3.org/TR/micropub/)
    server implementations.
    Configuration
    -------------
    `current_app.config` should contain the following configuration details:
    * `TOKEN_ENDPONT` (e.g. "https://tokens.indieauth.org/token")
    * `ME` (e.g. "http://example.com")
    Example Usage
    -------------
        from flask_indieauth import requires_indieauth
        @app.route('/micropub', methods=['GET','POST'])
        @requires_indieauth
        def handle_micropub():
            ...
    When a Flask route is wrapped in @requires_indieauth, this extension
    will look for an IndieAuth bearer token in these locations in order:
    * HTTP header `Authorization: Bearer xxx...`
    * HTTP form data in the parameter `access_token`
    * HTTP POST body, if in JSON format, in the `access_token` attribute
    If an access token is found, it is checked for a `me` value equal to the
    domain in current_app.config["ME"] and a `scope` value of `post` or `create`.
    If all checks pass, processing is passed to the Flask route handler.
"""

from functools import wraps
from flask import request, Response, current_app, g, session
import json
try:
    # For Python 3.0 and later
    from urllib.request import Request, urlopen
except ImportError:
    # Fallback to Python2 urllib2
    from urllib2 import Request, urlopen
try:
    # Python 3.0
    from urllib.parse import urlparse, parse_qs
except ImportError:
    # Fallback to Python2 urlparse
    from urlparse import urlparse, parse_qs

def requires_indieauth(f):
    """Wraps a Flask handler to require a valid IndieAuth access token.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        access_token = get_access_token()
        resp = check_auth(access_token)
        if isinstance(resp, Response):
          return resp
        return f(*args, **kwargs)
    return decorated

def check_auth(access_token):
    """This function contacts the configured IndieAuth Token Endpoint
    to see if the given token is a valid token and for whom.
    """
    if not access_token:
      current_app.logger.error('No access token.')
      return deny('No access token found.')

    request = Request(
      current_app.config['TOKEN_ENDPOINT'],
      headers={"Authorization": ("Bearer %s" % access_token)}
    )
    contents = urlopen(request).read().decode('utf-8')
    token_data = json.loads(contents)

    me = token_data['me']
    client_id = token_data['client_id']
    if me is None or client_id is None:
        current_app.logger.error("Invalid token [%s]" % contents)
        return deny('Invalid token')

    me, me_error = check_me(me)
    if me is None:
        current_app.logger.error("Invalid `me` value [%s]" % me_error)
        return deny(me_error)

    scope = token_data['scope']
    if not isinstance(scope, str):
        scope = scope[0]
    valid_scopes = ('post','create', 'read', 'follow', 'mute', 'block', 'channels')
    scope_ = scope.split()
    scope_valid = any((val in scope_) for val in valid_scopes)

    if not scope_valid:
        current_app.logger.error("Scope '%s' does not contain 'post' or 'create'." % scope)
        return deny("Scope '%s' does not contain 'post' or 'create'." % scope)

    g.user = {
      'me': me,
      'client_id': client_id,
      'scope': scope,
      'access_token': access_token
    }   

def check_me(me):
  token_me_base = (urlparse(me)).netloc
  me_base = (urlparse(current_app.config["ME"])).netloc
  if (me_base != token_me_base):
    return (None, "token me (%s) doesn't match ours (%s)" % (token_me_base, me_base))
  return (me, None)

def deny(reason):
    """Sends a 400 response because token is missing or bad"""
    return Response(reason, 400)

def get_access_token():
    access_token = request.headers.get('Authorization')
    if access_token:
      access_token = access_token.replace('Bearer ', '')
    if not access_token:
      access_token = request.form.get('access_token')
    if not access_token:
      access_token = get_access_token_from_json_request(request)
    if not access_token:
        access_token = session.get("access_token")
    return access_token

def get_access_token_from_json_request(request):
    try:
        jsondata = json.loads(request.get_data(as_text=True))
        return jsondata['access_token']
    except ValueError:
        return None