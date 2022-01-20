import datetime

import indieweb_utils
import requests

from config import MICROPUB_TOKEN

def post_syndication_change(source, target, syndication_target, location_header):
    if target == syndication_target and source.startswith("https://jamesg.blog"):
        if location_header and location_header != "":
            micropub_url = "https://micropub.jamesg.blog/micropub"

            requests.post(
                micropub_url,
                data={
                    "action": "update",
                    "url": source,
                    "add": {
                        "syndication": location_header
                    }
                },
                headers={
                    "Authorization": "Bearer " + MICROPUB_TOKEN
                }
            )


def send_webmention(source, target, is_validating=False):
    endpoint, message = indieweb_utils.discover_webmention_endpoint(target)

    if endpoint is None:
        return "There was an error sending the webmention", []
    
    # make post request to endpoint with source and target as values
    r = requests.post(
        endpoint,
        data={
            "source": source,
            "target": target
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        }
    )

    if r.headers and r.headers.get("Location"):
        location_header = r.headers.get("Location")
    else:
        location_header = ""

    if r.status_code == 200 or r.status_code == 201 or r.status_code == 202:
        message = "Webmention accepted"
    else:
        try:
            message = str(r.json())
        except:
            message = r.text

    # add syndication links to posts if necessary
    if is_validating is True:
        post_syndication_change(source, target, "https://brid.gy/publish/twitter", location_header)
        post_syndication_change(source, target, "https://micro.blog/", location_header)

    return message, [source, target, str(datetime.datetime.now()), r.status_code, message, endpoint, location_header, "", 1]