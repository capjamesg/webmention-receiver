# implementation of the post type discovery spec
# see spec on the IndieWeb wiki: https://indieweb.org/post-type-discovery
# this implementation is based on this code: https://github.com/capjamesg/indieweb-search/blob/main/crawler/post_type_discovery.py
# below, poke-of and reacji support have been added

from bs4 import BeautifulSoup
import emoji

def get_post_type(h_entry):
    post = h_entry.get("properties")

    if post == None:
        return "unknown"

    values_to_check = [
        ("rsvp", "rsvp"),
        ("in-reply-to", "reply"),
        ("repost-of", "repost"),
        ("like-of", "like"),
        ("video", "video"),
        ("photo", "photo"),
        ("summary", "summary"),
        ("poke-of", "poke")
    ]

    for item in values_to_check:
        if post.get(item[0]):
            return item[1]

    post_type = "note"

    if post.get("name") == None or post.get("name")[0] == "":
        return post_type

    title = post.get("name")[0].strip().replace("\n", " ").replace("\r", " ")

    content = post.get("content")

    if content in emoji.UNICODE_EMOJI:
        return "reacji"

    if content and content[0].get("text") and content[0].get("text")[0] != "":
        content = BeautifulSoup(content[0].get("text"), "lxml").get_text()

    if content and content[0].get("html") and content[0].get("html")[0] != "":
        content = BeautifulSoup(content[0].get("html"), "lxml").get_text()

    if not content.startswith(title):
        return "article"

    return "note"