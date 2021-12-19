from bs4 import BeautifulSoup
import ipaddress
import datetime
import requests

def send_function(source, target):
    if not (source.startswith("http://") or source.startswith("https://")) or not (target.startswith("http://") or target.startswith("https://")):
        message = "Source and target must use http:// or https:// protocols."
        return message, None

    # set up bs4
    try:
        r = requests.get(target, allow_redirects=True, timeout=10)
    except:
        message = "Error: Could not connect to target URL."
        return message, None

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
        return message, None

    try:
        endpoint_as_ip = ipaddress.ip_address(endpoint)

        if endpoint.is_private == True or endpoint.is_multicast == True \
            or endpoint_as_ip.is_loopback == True or endpoint_as_ip.is_unspecified == True \
                or endpoint_as_ip.is_reserved == True or endpoint_as_ip.is_link_local == True:
            message = "The endpoint does not connect to an accepted IP address."
            return message, None
    except ValueError:
        pass

    if endpoint == "localhost":
        message = "localhost is not a valid endpoint."
        return message, None

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

    if r.headers and r.headers.get("Location"):
        location_header = r.headers.get("Location")
    else:
        location_header = ""

    try:
        message = str(r.json())
    except:
        message = r.text

    return message, [source, target, str(datetime.datetime.now()), r.status_code, message, endpoint, location_header]