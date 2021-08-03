import sqlite3
import mf2py
import mf2util
import requests
from bs4 import BeautifulSoup

def validate_webmentions():
    connection = sqlite3.connect("webmentions.db")
    
    cursor = connection.cursor()

    with connection:
        get_webmentions_for_url = cursor.execute("SELECT source, target FROM webmentions WHERE status = 'validating'").fetchall()

        for u in get_webmentions_for_url:
            source = u[0]
            target = u[1]

            print("processing webmention from {} to {}".format(source, target))
                
            # Only allow 3 redirects before raising an error
            session = requests.Session()
            session.max_redirects = 3

            try:
                check_source_size = session.head(source, timeout=5)
            except requests.exceptions.TooManyRedirects:
                contents = "Source redirected too many times."
                cursor.execute("UPDATE webmentions SET status = ? WHERE source = ? and target = ?", (contents, source, target))

                continue
            except requests.exceptions.TimeoutError:
                contents = "Source timed out."
                cursor.execute("UPDATE webmentions SET status = ? WHERE source = ? and target = ?", (contents, source, target))

                continue
        
            if check_source_size.status_code != 200:
                contents = "Webmention target is invalid."
                cursor.execute("UPDATE webmentions SET status = ? WHERE source = ? and target = ?", (contents, source, target))

                continue
        
            if "text/html" not in check_source_size.headers["Content-Type"]:
                contents = "This endpoint only supports HTML webmentions."
                cursor.execute("UPDATE webmentions SET status = ? WHERE source = ? and target = ?", (contents, source, target))

                continue

            # If source size is greater than 10 megabytes
            if check_source_size.headers.get("content-length"):
                if int(check_source_size.headers["content-length"]) > 10000000:
                    contents = "Source is too large."
                    cursor.execute("UPDATE webmentions SET status = ? WHERE source = ? and target = ?", (contents, source, target))

                    continue
            
            get_source_for_validation = session.get(source).text

            soup = BeautifulSoup(get_source_for_validation, "html.parser")

            all_anchors = soup.find_all("a")
            contains_valid_link_to_target = False

            for a in all_anchors:
                if a["href"] == target:
                    contains_valid_link_to_target = True

            # Might want to comment out this if statement for testing
            if contains_valid_link_to_target == False:
                contents = "Document must contain source URL."
                cursor.execute("UPDATE webmentions SET status = ? WHERE source = ? and target = ?", (contents, source, target))

                continue

            parse = mf2py.Parser(url=source)
            
            parsed_h_entry = mf2util.interpret_comment(parse.to_dict(), source, target)

            # Convert webmention published date to a readable timestamp rather than a datetime object per default (returns error and causes malformed parsing)
            parsed_h_entry["published"] = parsed_h_entry["published"].strftime("%m/%d/%Y %H:%M:%S")

            if parsed_h_entry.get("author"):
                author_photo = parsed_h_entry["author"].get("photo")
                author_url = parsed_h_entry["author"].get("url")
                author_name = parsed_h_entry["author"].get("name")
            else:
                author_photo = None
                author_url = None
                author_name = None

            if parsed_h_entry.get("content-plain"):
                content = parsed_h_entry["content-plain"]
            else:
                content = None
            
            if parsed_h_entry.get("content"):
                content_html = parsed_h_entry["content"]
            else:
                content_html = None

            cursor.execute("UPDATE webmentions SET contents = ?, property = ?, author_name = ?, author_photo = ?, author_url = ?, content_html = ?, status = ? WHERE source = ? AND target = ?",(content, parsed_h_entry["type"], author_name, author_photo, author_url, content_html, "valid", source, target, ))
            
            connection.commit()

        print("{} Webmentions processed.".format(len(get_webmentions_for_url)))

validate_webmentions()

