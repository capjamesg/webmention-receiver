import indieweb_utils
import datetime
import requests

def send_function(source, target):
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

    return message, [source, target, str(datetime.datetime.now()), r.status_code, message, endpoint, location_header]