from bs4 import BeautifulSoup
import send_function
import sqlite3
import mf2py
import mf2util
import string
import random
import requests
import datetime
# from create_rss_feed import generate_feed
import emoji

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

def process_pending_webmention(item, cursor):
    feed_url = item[0]

    last_url_sent = cursor.execute("SELECT feed_url, last_url_sent FROM webhooks WHERE feed_url = ?;", (feed_url, )).fetchone()

    parsed = mf2py.Parser(url=feed_url).to_dict()

    # find h_feed item
    h_feed = [item["children"] for item in parsed['items'] if item['type'] == ['h-feed'] or item['type'] == "h-feed"]

    # get all h-entries
    if h_feed:
        entries = [item for item in h_feed[0] if item['type'] == 'h-entry' or item['type'] == ["h-entry"]]
    else:
        entries = [item for item in parsed["items"] if item['type'] == 'h-entry' or item['type'] == ["h-entry"]]

    domain = feed_url.split("/")[2]

    if len(entries) > 0:
        if last_url_sent != None:
            last_url_sent = last_url_sent[1]
        else:
            last_url_sent = ""

        last_url_sent = ""
        
        if last_url_sent != entries[0]['properties']['url'][0]:
            for entry in entries:
                if last_url_sent == entry['properties']['url'][0]:
                    break

                get_page = requests.get(entry['properties']['url'][0])

                if get_page.status_code == 200:

                    soup = BeautifulSoup(get_page.text, 'html.parser')

                    if soup.select(".e-content"):
                        soup = soup.select(".e-content")[0]
                    else:
                        continue

                    links = [link.get("href") for link in soup.find_all('a') if link.get("href") and not link.get("href").startswith("https://" + domain) \
                        and not link.get("href").startswith("http://" + domain) \
                        and not link.get("href").startswith("/") and not link.get("href").startswith("#") and not link.get("href").startswith("javascript:")]

                    links = list(set(links))

                    for url in links:
                        _, item = send_function.send_function(url, entry['properties']['url'][0])

                        if item == None:
                            continue

                        # Add webmentions to sent_webmentions table
                        
                        cursor.execute("INSERT INTO sent_webmentions (source, target, sent_date, status_code, response, webmention_endpoint, location_header) VALUES (?, ?, ?, ?, ?, ?, ?)", tuple(item) )
                        print("Webmention sent to " + item[0] + " from " + item[1])
                    
    if not last_url_sent:
        cursor.execute("INSERT INTO webhooks (feed_url, last_url_sent) VALUES (?, ?)", (feed_url, entries[0]['properties']['url'][0]))
    else:
        cursor.execute("UPDATE webhooks SET last_url_sent = ? WHERE feed_url = ?", (entries[0]['properties']['url'][0], feed_url))

def validate_webmentions():
    connection = sqlite3.connect(ROOT_DIRECTORY + "webmentions.db")
    
    cursor = connection.cursor()

    with connection:
        get_pending_webmentions = cursor.execute("SELECT to_check FROM pending_webmentions;").fetchall()

        for item in get_pending_webmentions:
            try:
                process_pending_webmention(item, cursor)
            except Exception as e:
                print(e)
                continue
            
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

            if soup.select(".u-poke-of") or soup.select(".poke-of"):
                post_type = "poke-of"

            if parsed_h_entry.get("content") and parsed_h_entry.get("content") in emoji.UNICODE_EMOJI:
                post_type = "reacji"

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

# generate_feed()