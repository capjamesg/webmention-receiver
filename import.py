import sqlite3
import json

connection = sqlite3.connect("webmentions.db")

def validate(webmention, *to_validate):
    if len(to_validate) == 1:
        if webmention.get(to_validate[0]):
            return webmention.get(to_validate[0])
        else:
            return ""
    else:
        if webmention.get(to_validate[0]) and webmention.get(to_validate[1]):
            return webmention.get(to_validate[0]).get(to_validate[1])
        else:
            return ""
        

with connection:
    cursor = connection.cursor()

    with open("old.json", "r") as f:
        old_webmentions = json.load(f)

    for webmention in old_webmentions["children"]:
        author_name = validate(webmention, "author", "name")
        author_photo = validate(webmention, "author", "photo")
        author_url = validate(webmention, "author", "url")
        content_html = validate(webmention, "content", "html")
        contents = validate(webmention, "content", "text")
        property = validate(webmention, "wm-property")
        received_date = validate(webmention, "wm-received")
        source = validate(webmention, "wm-source")
        target = validate(webmention, "wm-target")

        status = "valid"

        cursor.execute("INSERT INTO webmentions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (None, source, target, property, contents, author_name, author_photo, author_url, content_html, received_date, status))

        print("added webmention from {} to {} to db".format(source, target))