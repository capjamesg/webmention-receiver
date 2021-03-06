import datetime
import random
import sqlite3
import string
from typing import ItemsView

import indieweb_utils
import mf2py
import mf2util
import requests
from bs4 import BeautifulSoup

from config import (CLIENT_ID, ME, RSS_DIRECTORY, WEBHOOK_API_KEY,
                    WEBHOOK_SERVER, WEBHOOK_URL)
from create_rss_feed import generate_feed
from send import send_function


def final_checks(cursor, entry, url):
    # if item in db, don't add again
    in_db = cursor.execute(
        "SELECT * FROM sent_webmentions WHERE source = ? and target = ?",
        (entry["properties"]["url"][0], url),
    ).fetchone()

    if in_db:
        return

    _, item = send_function.send_webmention(
        entry["properties"]["url"][0], url, is_validating=True
    )

    if len(item) == 0:
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

    print("Webmention sent to " + item[0] + " from " + item[1])


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
    h_feed = None

    for item in parsed["items"]:
        if item["type"] == ["h-feed"]:
            h_feed = item

    entries = []

    # get all h-entry objects
    if h_feed:
        for item in h_feed["children"]:
            if item["type"] == ["h-entry"]:
                entries.append(item)
    else:
        for item in parsed["items"]:
            if item["type"] == ["h-entry"]:
                entries.append(item)

    domain = feed_url.split("/")[2]

    if len(entries) > 0:
        if last_url_sent is not None:
            last_url_sent = last_url_sent[1]
        else:
            last_url_sent = ""

        last_url_sent = ""

        if (
            entries[0]
            and entries[0].get("properties", {}).get("url")
            and last_url_sent != entries[0]["properties"]["url"][0]
        ):
            for entry in entries:
                if last_url_sent == entry["properties"]["url"][0]:
                    break

                try:
                    canonicalized_url = indieweb_utils.canonicalize_url(
                        entry["properties"]["url"][0],
                        domain,
                        entry["properties"]["url"][0],
                    )
                    get_page = requests.get(canonicalized_url)
                except:
                    continue

                if get_page.status_code == 200:
                    soup = BeautifulSoup(get_page.text, "lxml")

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
                        url = indieweb_utils.canonicalize_url(url, domain, url)

                        entry["properties"]["url"][0] = indieweb_utils.canonicalize_url(
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
            "SELECT source, target, vouch FROM webmentions WHERE status = 'validating';"
        ).fetchall()

        vouch_list = cursor.execute("SELECT domain FROM vouch;").fetchall()

        for item in get_webmentions_for_url:
            source = item[0]
            target = item[1]
            vouch = item[2]

            print(f"processing webmention from {source} to {target}")

            is_valid, moderate = indieweb_utils.validate_webmention(
                source, target, vouch, vouch_list
            )

            if is_valid == False:
                cursor.execute(
                    "UPDATE webmentions SET status = ? WHERE source = ? and target = ?",
                    ("invalid", source, target),
                )
                print(f"invalid webmention from {source} to {target}")

            parse = mf2py.Parser(url=source)

            parsed_h_entry = mf2util.interpret_comment(parse.to_dict(), source, target)

            # Convert webmention published date to a readable timestamp rather than a datetime object
            # per default (returns error and causes malformed parsing)
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

            h_entry = [
                item for item in parse.to_dict()["items"] if item["type"] == ["h-entry"]
            ]

            if len(h_entry) > 0:
                post_type = indieweb_utils.get_post_type(h_entry[0])
            else:
                post_type = "reply"

            cursor.execute(
                """
                UPDATE webmentions SET contents = ?,
                    property = ?,
                    author_name = ?,
                    author_photo = ?,
                    author_url = ?,
                    content_html = ?,
                    status = ?,
                    approved_to_show = ? 
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
                    source,
                    target,
                ),
            )

            connection.commit()

            print(f"done with {source}")

        print(f"{len(get_webmentions_for_url)} Webmentions processed.")


validate_webmentions()

generate_feed()
