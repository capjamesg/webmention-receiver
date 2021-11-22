# Python Webmention Receiver

This project contains the source code for a webmention receiver. There is also an endpoint for sending webmentions in this codebase.

If you have not heard of webmentions, I would encourage you to check out the [IndieWeb wiki webmentions page](https://indieweb.org/Webmention) to learn more. In short, webmentions are a way for you to send a message from one website to another. This approach lets you maintain control over your own content while also allowing you to share your content with others.

To use this project, you will need to replace all mentions of "jamesg.blog" with your own domain name in the codebase.

## Screenshot

![Microsub channel list](screenshot.png)

## API Endpoints

The webmention receiver comes with a few API endpoints that may be useful.

### Send a Webmention

The following endpoint lets you send a webmention via API. This endpoint is open to anyone, including visitors who are not authenticated with your endpoint. You may want to use this endpoint to let people submit webmentions from a form on your website.

    POST /send/open

    {
        "source": "https://jamesg.blog/webmention.html",
        "target": "https://jamesg.blog/post.html",
    }

This endpoint will return a 201 wstatus code if the webmention was successfully sent.

### Discover a Webmention Endpoint

You can use the /discover endpoint to find the webmention endpoint associated with a site, if one is specified.

    POST /discover

    {
        "target": "https://jamesg.blog"
    }

This endpoint will return a response like:

    {"success": True, "endpoint": "https://webmention.jamesg.blog/webmention"}

### Get Webmentions for a Page

You can retrieve webmentions for a specific page using the API. Here is the request you need to make, where URL is the URL of the page for which you want to retrieve webmentions:

    GET /received?target=URL

This endpoint will return an object like this:

    {
        "count": 1,
        "count_by_property": {
            "like-of": 1,
        },
        "webmentions": [
            {
                "approved_to_show": 1,
                "author_name": "Ryan Barrett",
                "author_photo": "https://webmention.jamesg.blog/static/images/ycaoqndg.jpeg",
                "author_url": "https://snarfed.org/",
                "content_html": "likes <a class=\"u-like u-like-of\" href=\"https://jamesg.blog/2021/11/16/i-love-my-website\">I love my website | James’ Coffee Blog</a>",
                "contents": "likes I love my website | James’ Coffee Blog",
                "property": "like-of",
                "received_date": "2021-11-16 14:31:50.407750",
                "source": "https://snarfed.org/2021-11-16_i-love-my-website-james-coffee-blog",
                "status": "valid",
                "target": "https://jamesg.blog/2021/11/16/i-love-my-website",
                "vouch": null
            },
        ]
    }

The "count" value tells you how many webmentions have been sent to a specific page. The webmention types that can appear in count_by_property are:

- like-of
- in-reply-to
- bookmark-of
- poke-of
- repost-of

By default, this endpoint only returns webmentions that have been approved to show.

Webmentions are approved to show by default. However, you can hide a webmention in the admin dashboard. This may be useful for spam prevention.

You can also delete a webmention from the admin dashboard. Deleting a webmention means it will be removed from the database.

## Endpoints

Here are the endpoints supported by this project:

- / - Endpoint for receiving webmentions.
- /home - See the webmentions you have received.
- /sent - See webmentions you have sent.
- /send - Endpoint to send a webmention.
- /send/open - Open endpoint for anyone to submit a webmention to my site. Used on my "Submit a webmention" forms on my blog posts.
- /retrieve - See webmentions you have received in JSON.

## webmention.rocks Validation

[webmention.rocks](https://webmention.rocks/) is being used to test compliance with the webmention specification for receiving and sending webmentions.

## Vouch Support

This project is capable of sending and processing [Vouch](https://indieweb.org/Vouch) Webmentions as per the Vouch specification. The Vouch specification was designed to help prevent against spam. Vouch lets a sender specify a URL owned by a third party that will "vouch" for them. The webmention reciever checks if the "Vouch" domain is on an approved list. If the receiver trusts the vouch domain, the receiver will then go on to make sure that the specified URL links to their site. If the vouch link contains a hyperlink to the sender's URL, the specification states you can trust the webmention. Otherwise, the webmention is flagged as "needs approval".

Please refer to the IndieWeb wiki [Vouch](https://indieweb.org/Vouch) page for more information on how to send and receive a Vouch.

To configure Vouch, you will need to add all of the domains you trust to the your vouch list on the /vouch web page. These are domains from whom you will accept a vouch so long as the "vouch" URL the sender specifies links to your blog.

### Sending a webmention with vouch

To send a Vouch webmention, you can specify an optional "Vouch" URL when you go to send a webmention. If one is not specified, a vouch is not sent with your webmention. Please note that not all webmention receivers will accept a vouch. Vouch is a separate specification. The Webmention spec does not require a receiver to implement Vouch support to be compliant with the spec.

## Sender Discovery Compliance

This repository has passed tests in the "sender discovery" category.

- https://webmention.rocks/test/1
- https://webmention.rocks/test/2
- https://webmention.rocks/test/3
- https://webmention.rocks/test/4
- https://webmention.rocks/test/5
- https://webmention.rocks/test/6
- https://webmention.rocks/test/7
- https://webmention.rocks/test/8
- https://webmention.rocks/test/9
- https://webmention.rocks/test/10
- https://webmention.rocks/test/11
- https://webmention.rocks/test/12
- https://webmention.rocks/test/13
- https://webmention.rocks/test/14
- https://webmention.rocks/test/15
- https://webmention.rocks/test/16
- https://webmention.rocks/test/17
- https://webmention.rocks/test/18
- https://webmention.rocks/test/19
- https://webmention.rocks/test/20
- 21 IN PROGRESS
- https://webmention.rocks/test/22
- https://webmention.rocks/test/23

Please refer to the [webmention.rocks](https://webmention.rocks/) website for specifics on each of these tests and what they mean.

## Reciever Tests

This application has passed the following receiver tests:

- https://webmention.rocks/receive/1
- https://webmention.rocks/receive/2

## How to set up

To set up this project, first configure a Python virtual environment:

    virtualenv venv
    source venv/bin/activate

Then you should install the dependencies necessary to run this project:

    pip install -r requirements.txt

### Configuration variables

You will then need to create a .env file. This file should contain an API key that you keep to yourself:

    api-key=THIS_IS_YOUR_KEY

Please also read the config.py file and populate it with the correct values.

You will need to specify the callback URL for your webmention endpoint, your client ID, your token endpoint, your domain name, and the directory in which your RSS feed should be placed.

Examples are provided in the config.py file.

### Setting up the database

To set up the database for this project, execute the following command:

    flask seed create-tables

The command above creates the database tables for this project.

Now you are ready to use the endpoint. To run the server, run this command:

    flask run

In accordance with the webmention specification, the webmention receiver processes webmentions asynchronously. I use cron to process webmentions every hour.

To process webmentions, you should set up a cron job that executes the validate_webmention.py script. An example cron job you could use is:

    0 * * * * python3 /path/to/webmention_receiver/validate_webmention.py

api-key should be equal to the value of api-key that you set in your .env file.

## Configuring Automatic Webmention Sending

You can request that mentions are sent to all links in a h-feed as soon as you publish a resource on your website.

This is useful if you want people who use webmentions to get notified when you link to their content without having to manually send webmentions to each link.

You can do this by triggering the following webhook after your site has been deployed:

    https://yourwebmentionendpoint.com/webhook?url=https://yourdomain.com/

This webhook can be triggered for any URL on your site that contains a h-feed.

## License

This project is licenced under the MIT License.

## Contributing

If you have ideas on how to make this webmention endpoint better, feel free to create an Issue for discussion on the GitHub Issues page.

## Contributors

- capjamesg