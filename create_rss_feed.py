from feedgen.feed import FeedGenerator
import dateutil
import sqlite3

fg = FeedGenerator()

def generate_feed():
    fg.id("https://webmention.jamesg.blog")
    fg.title("James' Webmention Receiver Feed")
    fg.author(name="James' Webmention Receiver")
    fg.link(href="https://webmention.jamesg.blog", rel="self")
    fg.logo("https://webmention.jamesg.blog/static/favicon.ico")
    fg.subtitle("James' Webmention Receiver Feed")
    fg.description("Webmentions sent to webmention.jamesg.blog")
    fg.language("en")

    connection = sqlite3.connect("/home/capjamesg/webmentions.db")

    with connection:
        cursor = connection.cursor()
        # Create RSS feed for all webmentions
        # Exclude Bridgy webmentions as I may receive a lot of them
        webmentions = cursor.execute("SELECT source, target, received_date, contents, property, author_name FROM webmentions WHERE source NOT LIKE 'https://brid.gy/%' AND status = 'valid' ORDER BY received_date DESC LIMIT 10;").fetchall()
        for webmention in webmentions:

            if webmention[4] == "like-of":
                post_type = "❤️ Like"
            elif webmention[4] == "mention-of":
                post_type = "💬 Mention"
            elif webmention[4] == "bookmark-of":
                post_type = "🔖 Bookmark"
            else:
                post_type = "💬 Webmention"

            fe = fg.add_entry()
            fe.id(webmention[0])

            if post_type and webmention[5] and webmention[1]:
                fe.title("{} from {} to {}".format(post_type, webmention[5], webmention[1]))
            else:
                fe.title(webmention[0])

            try:
                date = dateutil.parser.parse(webmention[2])

                timestamp = date.strftime("%Y-%m-%dT%H:%M:%S+00:00")
                fe.pubDate(timestamp)
            except:
                pass

            fe.link(href=webmention[0])

            if webmention[3]:
                fe.description(webmention[3])
            else:
                if webmention[5]:
                    # parse date
                    date = dateutil.parser.parse(webmention[2])

                    # show date as day date month year
                    date = date.strftime("%A %-d %M, %Y")

                    fe.description("""
                    <p>{} from {} to <a href="{}">{}</a>. Received on {}.</p>
                    """.format(post_type, webmention[5], webmention[1], webmention[1], date))
                else:
                    fe.description("""
                    <p>{} from {} to <a href="{}">{}</a>. Received on {}.</p>
                    """.format(post_type, webmention[0].split("//")[1].split("/")[0], webmention[1], webmention[1], date))

    fg.rss_file("/home/capjamesg/webmention_receiver/static/webmentions.xml")

    print("created webmentions.xml RSS feed")

if __name__ == "__main__":
    generate_feed()