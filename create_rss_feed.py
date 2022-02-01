import datetime
import sqlite3

import dateutil
from feedgen.feed import FeedGenerator

from config import RSS_DIRECTORY

fg = FeedGenerator()


def generate_feed():
    feed_text = """
    <feed>
        <title>James' Webmention Receiver Feed</title>
        <link href="https://webmention.jamesg.blog" rel="self" />
        <id>https://webmention.jamesg.blog</id>
        <generator uri="https://github.com/capjamesg/webmention-receiver">webmention-receiver</generator>
        <updated>{}</updated>
    """.format(
        datetime.datetime.now().isoformat()
    )

    connection = sqlite3.connect(RSS_DIRECTORY + "/webmentions.db")

    with connection:
        cursor = connection.cursor()
        # Create RSS feed for all webmentions
        # Exclude Bridgy webmentions as I may receive a lot of them
        webmentions = cursor.execute(
            """SELECT
            source,
            target,
            received_date,
            contents,
            property,
            author_name,
            post_title
            FROM webmentions
            WHERE status = 'valid'
            ORDER BY received_date DESC LIMIT 10;"""
        ).fetchall()

        for webmention in webmentions:
            if webmention[4] == "like-of":
                post_type = ("❤️", "liked")
            elif webmention[4] == "favorite-of":
                post_type = ("❤️", "liked")
            elif webmention[4] == "mention-of":
                post_type = ("💬", "mentioned you in")
            elif webmention[4] == "quotation-of":
                post_type = ("📔", "quoted you in")
            elif webmention[4] == "repost-of":
                post_type = ("🔁", "reposted")
            elif webmention[4] == "bookmark-of":
                post_type = ("🔖", "bookmarked")
            else:
                post_type = ("💬", "replied to")

            new_entry = """
                <entry>
                    <id>{}</id>
            """.format(
                webmention[0]
            )

            if post_type and webmention[5] and webmention[1]:
                new_entry += """
                    <title></title>
                """
            else:
                new_entry += """
                    <title>{}</title>
                """.format(
                    webmention[0]
                )

            try:
                date = dateutil.parser.parse(webmention[2])

                timestamp = date.strftime("%Y-%m-%dT%H:%M:%S+00:00")
                new_entry += """
                    <published>{}</published>
                    <updated>{}</updated>
                """.format(
                    timestamp, timestamp
                )
            except:
                pass

            new_entry += """
                <link href="{}" />
            """.format(
                webmention[0]
            )

            if webmention[3]:
                new_entry += """
                    <content type="html">{}</content>
                """
            else:
                if webmention[3]:
                    # parse date
                    date = dateutil.parser.parse(webmention[2])

                    # show date as day date month year
                    date = date.strftime("%d %b, %Y")

                    new_entry += """
                    <content type="html"><p>{}</p><p>{} {} {} <a href="{}">{}</a>.</p></content>
                    """.format(
                        webmention[3],
                        post_type[0],
                        webmention[5],
                        post_type[1],
                        webmention[1],
                        webmention[6],
                    )
                else:
                    new_entry += """
                    <content type="html"><p>{} {} {} <a href="{}">{}</a>.</p></content>
                    """.format(
                        post_type[0],
                        webmention[5],
                        post_type[1],
                        webmention[1],
                        webmention[6],
                    )

            new_entry += "</entry>"
            feed_text += new_entry

    feed_text += "</feed>"

    with open("/home/james/webmention_receiver/static/webmentions.xml", "w") as f:
        f.write(feed_text)

    print("created webmentions.xml RSS feed")


if __name__ == "__main__":
    generate_feed()
