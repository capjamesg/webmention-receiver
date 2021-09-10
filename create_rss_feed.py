from feedgen.feed import FeedGenerator
from config import ROOT_DIRECTORY
import sqlite3

fg = FeedGenerator()

def generate_feed():
    fg.id("https://webmention.jamesg.blog")
    fg.title("James' Webmention Receiver Feed")
    fg.author(name="James' Webmention Receiver")
    fg.link(href="https://webmention.jamesg.blog", rel="alternate")
    fg.logo("https://webmention.jamesg.blog/favicon.ico")
    fg.subtitle("James' Webmention Receiver Feed")
    fg.description("Webmentions sent to webmention.jamesg.blog")
    fg.language("en")

    connection = sqlite3.connect("webmentions.db")

    with connection:
        cursor = connection.cursor()
        # Create RSS feed for all webmentions
        # Exclude Bridgy webmentions as I may receive a lot of them
        webmentions = cursor.execute("SELECT source, target, received_date, contents FROM webmentions WHERE source NOT LIKE 'https://brid.gy/%' AND status = 'valid' ORDER BY received_date ASC LIMIT 10;").fetchall()
        for webmention in webmentions:
            fe = fg.add_entry()
            fe.id(webmention[0])
            fe.title(webmention[0])
            fe.link(href=webmention[3], rel='alternate')
            fe.link(href=webmention[2], rel='self')
            if webmention[3]:
                fe.description(webmention[3])
            else:
                fe.description("Webmention sent from {} to {} on {}.".format(webmention[0], webmention[1], webmention[2]))

    fg.rss_file("static/webmentions.xml")

    print("created webmentions.xml RSS feed")

generate_feed()