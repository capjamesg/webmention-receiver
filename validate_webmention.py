import sqlite3
import mf2py
import mf2util
import string
import random
import requests
import datetime
from bs4 import BeautifulSoup
from create_rss_feed import generate_feed

ROOT_DIRECTORY = "/home/capjamesg/"

def validate_headers(request_item, cursor, source, target):
    validated = True
    if request_item.headers.get("Content-Length"):
        if int(request_item.headers["Content-Length"]) > 10000000:
            contents = "Source is too large."
            cursor.execute("UPDATE webmentions SET status = ? WHERE source = ? and target = ?", (contents, source, target))

            validated = False

    if "text/html" not in request_item.headers["Content-Type"]:
        contents = "This endpoint only supports HTML webmentions."
        cursor.execute("UPDATE webmentions SET status = ? WHERE source = ? and target = ?", (contents, source, target))

        validated = False

    return validated

def validate_webmentions():
    connection = sqlite3.connect(ROOT_DIRECTORY + "/webmentions.db")
    
    cursor = connection.cursor()

    with connection:
        get_webmentions_for_url = cursor.execute("SELECT source, target FROM webmentions WHERE status = 'validating';").fetchall()

        for u in get_webmentions_for_url:
            source = u[0]
            target = u[1]
            print("processing webmention from {} to {}".format(source, target))
                
            # Only allow 3 redirects before raising an error
            session = requests.Session()
            session.max_redirects = 3

            try:
                check_source_size = session.head(source, timeout=5)

                validated_headers = validate_headers(check_source_size, cursor, source, target)
            except requests.exceptions.TooManyRedirects:
                contents = "Source redirected too many times."
                cursor.execute("UPDATE webmentions SET status = ? WHERE source = ? and target = ?", (contents, source, target))

                continue
            except requests.exceptions.TimeoutError:
                contents = "Source timed out."
                cursor.execute("UPDATE webmentions SET status = ? WHERE source = ? and target = ?", (contents, source, target))

                continue

            get_source_for_validation = session.get(source).text

            if not validated_headers:
                validated_headers = validate_headers(check_source_size, cursor, source, target)
        
            if check_source_size.status_code == 410:
                # Support deleted webmention in line with the spec
                cursor.execute("DELETE FROM webmentions WHERE source = ?;", (source, ))

                continue
            if check_source_size.status_code != 200:
                contents = "Webmention target is invalid."
                cursor.execute("UPDATE webmentions SET status = ? WHERE source = ? and target = ?", (contents, source, target))

                continue
            
            soup = BeautifulSoup(get_source_for_validation, "lxml")

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
                cursor.execute("UPDATE webmentions SET status = ? WHERE source = ? and target = ?", (contents, source, target))

                continue

            parse = mf2py.Parser(url=source)
            
            parsed_h_entry = mf2util.interpret_comment(parse.to_dict(), source, target)

            post_type = "reply"

            if parsed_h_entry.get("like-of") and parsed_h_entry.get("like-of"):
                post_type = "like-of"

            if parsed_h_entry.get("bookmark-of") and parsed_h_entry.get("bookmark-of"):
                post_type = "bookmark-of"

            # Convert webmention published date to a readable timestamp rather than a datetime object per default (returns error and causes malformed parsing)
            if parsed_h_entry.get("published"):
                parsed_h_entry["published"] = parsed_h_entry["published"].strftime("%m/%d/%Y %H:%M:%S")
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
                r = requests.get(author_photo)

                random_letters = "".join(random.choice(string.ascii_lowercase) for i in range(8))

                if "jpg" in author_photo:
                    extension = "jpg"
                elif "png" in author_photo:
                    extension = "png"
                elif "gif" in author_photo:
                    extension = "gif"
                else:
                    extension = "jpeg"

                if r.status_code == 200:
                    with open("/home/capjamesg/webmention_receiver/static/images/{}".format(random_letters + "." + extension), "wb+") as f:
                        f.write(r.content)

                author_photo = "https://webmention.jamesg.blog/static/images/" + random_letters + "." + extension

            if parsed_h_entry.get("content-plain"):
                content = parsed_h_entry["content-plain"]
            else:
                content = None
            
            if parsed_h_entry.get("content"):
                content_html = parsed_h_entry["content"]

                parsed_h_entry["content"] = parsed_h_entry["content"].replace("<a ", "<a rel='nofollow'>")
            else:
                content_html = None

            cursor.execute("UPDATE webmentions SET contents = ?, property = ?, author_name = ?, author_photo = ?, author_url = ?, content_html = ?, status = ? WHERE source = ? AND target = ?",(content, post_type, author_name, author_photo, author_url, content_html, "valid", source, target, ))
            
            connection.commit()

            print("done with {}".format(source))

        print("{} Webmentions processed.".format(len(get_webmentions_for_url)))

validate_webmentions()

generate_feed()