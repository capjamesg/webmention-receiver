import datetime
import random
import sqlite3
import string

import indieweb_utils
import mf2py
import mf2util
import requests
from bs4 import BeautifulSoup

from config import (CLIENT_ID, RSS_DIRECTORY, WEBHOOK_API_KEY, WEBHOOK_SERVER,
                    WEBHOOK_URL)
from create_rss_feed import generate_feed
from send import send_function


def canonicalize_url(url, domain, full_url=None):
    if url.startswith("http://") or url.startswith("https://"):
        return url
    elif url.startswith("//"):
        return "https:" + domain.strip() + "/" + url
    elif url.startswith("/"):
        return "https://" + domain.strip() + "/" + url
    elif url.startswith("./"):
        return full_url + url.replace(".", "")
    elif url.startswith("../"):
        return "https://" + domain.strip() + "/" + url[3:]
    else:
        return "https://" + url


def final_checks(cursor, entry, url):
    # if item in db, don't add again
    in_db = cursor.execute(
        "SELECT * FROM sent_webmentions WHERE source = ? and target = ?",
        (entry["properties"]["url"][0], url),
    ).fetchone()

    if in_db:
        return

    _, item = send_function.send_webmention(entry["properties"]["url"][0], url)

    if item == None or item == []:
        return

    # Add webmentions to sent_webmentions table

    cursor.execute(
        """
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
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        tuple(item),
    )


def process_vouch(vouch, cursor, source):
    # use vouch to flag webmentions for moderation
    # see Vouch spec for more: https://indieweb.org/Vouch
    moderate = False

    if vouch and vouch != "":
        vouch_domain = vouch.split("/")[2]

        if vouch_domain.endswith("jamesg.blog"):
            moderate = False

        if moderate == True:
            vouch_list = cursor.execute(
                "SELECT domain FROM vouch WHERE vouch_domain = ?", (vouch_domain,)
            ).fetchall()

            # only get domains
            vouch_list = [v[0] for v in vouch_list]

            if vouch_domain in vouch_list:
                try:
                    r = requests.get(vouch)
                except:
                    return moderate

                soup = BeautifulSoup(r.text, "lxml")

                # find hyperlink with source
                # required for a vouch to be valid
                for a in soup.find_all("a"):
                    if a.get("href"):
                        if a["href"] == source:
                            moderate = False

    return moderate


def validate_headers(request_item, cursor, source, target):
    validated = True
    if request_item.headers.get("Content-Length"):
        if int(request_item.headers["Content-Length"]) > 10000000:
            contents = "Source is too large."
            cursor.execute(
                "UPDATE webmentions SET status = ? WHERE source = ? and target = ?",
                (contents, source, target),
            )

            validated = False

    if "text/html" not in request_item.headers["Content-Type"]:
        contents = "This endpoint only supports HTML webmentions."
        cursor.execute(
            "UPDATE webmentions SET status = ? WHERE source = ? and target = ?",
            (contents, source, target),
        )

        validated = False

    return validated


def process_pending_webmention(item, cursor):
    feed_url = item[0]

    last_url_sent = cursor.execute(
        "SELECT feed_url, last_url_sent FROM webhooks WHERE feed_url = ?;", (feed_url,)
    ).fetchone()

    try:
        parsed = mf2py.Parser(url=feed_url).to_dict()
    except:
        return

    # find h_feed item
    h_feed = [
        item["children"]
        for item in parsed["items"]
        if item["type"] == ["h-feed"] or item["type"] == "h-feed"
    ]

    # get all h-entries
    if h_feed:
        entries = [
            item
            for item in h_feed[0]
            if item["type"] == "h-entry" or item["type"] == ["h-entry"]
        ]
    else:
        entries = [
            item
            for item in parsed["items"]
            if item["type"] == "h-entry" or item["type"] == ["h-entry"]
        ]

    domain = feed_url.split("/")[2]

    if len(entries) > 0:
        if last_url_sent != None:
            last_url_sent = last_url_sent[1]
        else:
            last_url_sent = ""

        last_url_sent = ""

        if (
            entries[0]["properties"].get("url")
            and last_url_sent != entries[0]["properties"]["url"][0]
        ):
            for entry in entries:
                if last_url_sent == entry["properties"]["url"][0]:
                    break

                try:
                    get_page = requests.get(
                        canonicalize_url(
                            entry["properties"]["url"][0],
                            domain,
                            entry["properties"]["url"][0],
                        )
                    )
                except:
                    continue

                if get_page.status_code == 200:

                    soup = BeautifulSoup(get_page.text, "html.parser")

                    if soup.select(".e-content"):
                        soup = soup.select(".e-content")[0]
                    else:
                        continue

                    links = [
                        link.get("href")
                        for link in soup.find_all("a")
                        if link.get("href")
                        and not link.get("href").startswith("https://" + domain)
                        and not link.get("href").startswith("http://" + domain)
                        and not link.get("href").startswith("/")
                        and not link.get("href").startswith("#")
                        and not link.get("href").startswith("javascript:")
                    ]

                    links = list(set(links))

                    for url in links:
                        url = canonicalize_url(url, domain, url)

                        entry["properties"]["url"][0] = canonicalize_url(
                            entry["properties"]["url"][0],
                            domain,
                            entry["properties"]["url"][0],
                        )

                        final_checks(cursor, entry, url)

            if not last_url_sent and entries[0]:
                cursor.execute(
                    "INSERT INTO webhooks (feed_url, last_url_sent) VALUES (?, ?)",
                    (feed_url, entries[0]["properties"]["url"][0]),
                )
            else:
                cursor.execute(
                    "UPDATE webhooks SET last_url_sent = ? WHERE feed_url = ?",
                    (entries[0]["properties"]["url"][0], feed_url),
                )


def validate_webmentions():
    connection = sqlite3.connect(RSS_DIRECTORY + "webmentions.db")

    cursor = connection.cursor()

    with connection:
        get_pending_webmentions = cursor.execute(
            "SELECT to_check FROM pending_webmentions;"
        ).fetchall()

        for item in get_pending_webmentions:
            process_pending_webmention(item, cursor)

        cursor.execute("DELETE FROM pending_webmentions;")

        get_webmentions_for_url = cursor.execute(
            "SELECT source, target, vouch, token FROM webmentions WHERE status = 'validating';"
        ).fetchall()

        for u in get_webmentions_for_url:
            source = u[0]
            target = u[1]
            vouch = u[2]
            token = u[3]

            headers = {"User-Agent": "webmention-endpoint-james"}

            # check if the source is a private webmention that requires authentication

            if token and token != "":
                try:
                    source_request = requests.head(
                        source, allow_redirects=True, timeout=5
                    )
                except:
                    contents = "Source URL could not be retrieved."
                    cursor.execute(
                        "UPDATE webmentions SET status = ? WHERE source = ? and target = ?",
                        (contents, source, target),
                    )
                    continue

                # check for www-authenticate header
                if source_request.headers.get("www-authenticate"):
                    link_headers = requests.utils.parse_header_links(
                        source_request["links"].rstrip(">").replace(">,<", ",<")
                    )

                    if link_headers.get("token_endpoint"):
                        token_endpoint = link_headers["token_endpoint"]["url"]
                    else:
                        contents = "Source URL does not contain a token endpoint."
                        cursor.execute(
                            "UPDATE webmentions SET status = ? WHERE source = ? and target = ?",
                            (contents, source, target),
                        )
                        continue
                else:
                    contents = "Source URL does not specify a token endpoint."
                    cursor.execute(
                        "UPDATE webmentions SET status = ? WHERE source = ? and target = ?",
                        (contents, source, target),
                    )
                    continue

                data = {"grant_type": "authorization_code", "code": token}

                try:
                    token_request = requests.post(
                        token_endpoint, data=data, allow_redirects=True, timeout=5
                    )
                except:
                    contents = "Token endpoint did not return a token."
                    cursor.execute(
                        "UPDATE webmentions SET status = ? WHERE source = ? and target = ?",
                        (contents, source, target),
                    )
                    continue

                if token_request.status_code != 200:
                    contents = "Token endpoint did not return a token."
                    cursor.execute(
                        "UPDATE webmentions SET status = ? WHERE source = ? and target = ?",
                        (contents, source, target),
                    )
                    continue

                token_to_send = token_request.json()["access_token"]

                headers = {"Authorization": "Bearer " + token_to_send}

            moderate = True

            print(f"processing webmention from {source} to {target}")

            # Only allow 3 redirects before raising an error
            session = requests.Session()
            session.max_redirects = 3

            try:
                check_source_size = session.head(source, timeout=5, headers=headers)

                validated_headers = validate_headers(
                    check_source_size, cursor, source, target
                )

                if check_source_size.status_code == 410:
                    # Support deleted webmention in line with the spec
                    cursor.execute(
                        "DELETE FROM webmentions WHERE source = ?;", (source,)
                    )

                    continue

            except requests.exceptions.TooManyRedirects:
                contents = "Source redirected too many times."
                cursor.execute(
                    "UPDATE webmentions SET status = ? WHERE source = ? and target = ?",
                    (contents, source, target),
                )

                continue
            except requests.exceptions.TimeoutError:
                contents = "Source timed out."
                cursor.execute(
                    "UPDATE webmentions SET status = ? WHERE source = ? and target = ?",
                    (contents, source, target),
                )

                continue
            except:
                contents = "Webmention failed. Reason unknown."
                cursor.execute(
                    "UPDATE webmentions SET status = ? WHERE source = ? and target = ?",
                    (contents, source, target),
                )
                continue

            try:
                get_source_for_validation = session.get(source, headers=headers)
            except Exception as e:
                print(e)
                continue

            if not validated_headers:
                validated_headers = validate_headers(
                    check_source_size, cursor, source, target
                )

            parse_page = BeautifulSoup(get_source_for_validation.text, "html.parser")

            # get all <link> tags
            meta_links = parse_page.find_all("link")

            for l in meta_links:
                # use meta http-equiv status spec to detect 410s https://indieweb.org/meta_http-equiv_status
                # detecting http-equiv status 410s is required by the webmention spec
                if l.get("http-equiv") and l.get("http-equiv") == "Status":
                    if l.get("content") == "410 Gone":
                        # Support deleted webmention in line with the spec
                        cursor.execute(
                            "DELETE FROM webmentions WHERE source = ?;", (source,)
                        )

                        continue

            if get_source_for_validation.status_code != 200:
                contents = "Webmention target is invalid."
                cursor.execute(
                    "UPDATE webmentions SET status = ? WHERE source = ? and target = ?",
                    (contents, source, target),
                )

                continue

            soup = parse_page

            all_anchors = soup.find_all("a")
            contains_valid_link_to_target = False

            for a in all_anchors:
                if a.get("href"):
                    if a["href"] == target:
                        contains_valid_link_to_target = True

            if target in get_source_for_validation:
                contains_valid_link_to_target = True

            # Might want to comment out this if statement for testing
            #  and not source.startswith("https://brid.gy/like/instagram") (not used anymore)
            if contains_valid_link_to_target == False:
                contents = "Document must contain source URL."
                cursor.execute(
                    "UPDATE webmentions SET status = ? WHERE source = ? and target = ?",
                    (contents, source, target),
                )

                continue

            moderate = process_vouch(vouch, cursor, source)

            parse = mf2py.Parser(url=source)

            parsed_h_entry = mf2util.interpret_comment(parse.to_dict(), source, target)

            target_request = requests.get(target, headers=headers)

            if target_request.status_code != 200:
                continue

            target_soup = BeautifulSoup(target_request.text, "html.parser")

            target_title = target_soup.find("title").text

            post_type = "reply"

            if parsed_h_entry == None:
                continue

            # Convert webmention published date to a readable timestamp rather than a datetime object per default (returns error and causes malformed parsing)
            if parsed_h_entry.get("published"):
                parsed_h_entry["published"] = parsed_h_entry["published"].strftime(
                    "%m/%d/%Y %H:%M:%S"
                )
            else:
                now = datetime.datetime.now()
                parsed_h_entry["published"] = now.strftime("%m/%d/%Y %H:%M:%S")

            if parsed_h_entry.get("author"):
                author_photo = parsed_h_entry["author"].get("photo")
                author_url = parsed_h_entry["author"].get("url")
                author_name = parsed_h_entry["author"].get("name")
            else:
                author_photo = None
                author_url = None
                author_name = None

            if author_photo:
                try:
                    r = requests.get(author_photo)

                    random_letters = "".join(
                        random.choice(string.ascii_lowercase) for i in range(8)
                    )

                    if "jpg" in author_photo:
                        extension = "jpg"
                    elif "png" in author_photo:
                        extension = "png"
                    elif "gif" in author_photo:
                        extension = "gif"
                    else:
                        extension = "jpeg"

                    if r.status_code == 200:
                        with open(
                            RSS_DIRECTORY
                            + f"/static/images/{random_letters + '.' + extension}",
                            "wb+",
                        ) as f:
                            f.write(r.content)

                    author_photo = (
                        CLIENT_ID + "/static/images/" + random_letters + "." + extension
                    )
                except:
                    pass

            if parsed_h_entry.get("content-plain"):
                content = parsed_h_entry["content-plain"]
            else:
                content = None

            if parsed_h_entry.get("content"):
                content_html = parsed_h_entry["content"]

                parsed_h_entry["content"] = parsed_h_entry["content"].replace(
                    "<a ", "<a rel='nofollow'>"
                )
            else:
                content_html = None

            post_type = indieweb_utils.get_post_type(parsed_h_entry)

            cursor.execute(
                """
                UPDATE webmentions SET contents = ?,
                    property = ?,
                    author_name = ?,
                    author_photo = ?,
                    author_url = ?,
                    content_html = ?,
                    status = ?,
                    approved_to_show = ?,
                    post_title = ?
                WHERE source = ? AND target = ?""",
                (
                    content,
                    post_type,
                    author_name,
                    author_photo,
                    author_url,
                    content_html,
                    "valid",
                    moderate,
                    target_title,
                    source,
                    target,
                ),
            )

            connection.commit()

            print(f"done with {source}")

        print(f"{len(get_webmentions_for_url)} Webmentions processed.")


validate_webmentions()

generate_feed()
