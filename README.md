# Python Webmention Receiver

This project contains the source code for a webmention receiver. There is also an endpoint for sending webmentions in this codebase.

If you have not heard of webmentions, I would encourage you to check out the [IndieWeb wiki webmentions page](https://indieweb.org/Webmention) to learn more. In short, webmentions are a way for you to send a message from one website to another. This approach lets you maintain control over your own content while also allowing you to share your content with others.

To use this project, you will need to replace all mentions of "jamesg.blog" with your own domain name in the codebase.

## Endpoints

Here are the endpoints supported by this project:

- / - Endpoint for receiving webmentions.
- /home - See the webmentions you have received.
- /sent - See webmentions you have sent.
- /send - Endpoint to send a webmention.
- /retrieve - See webmentions you have received in JSON.

## webmention.rocks Validation

[webmention.rocks](https://webmention.rocks/) is being used to test compliance with the webmention specification for receiving and sending webmentions.

## Sender Discovery Compliance

So far, this repository has passed tests in the "sender discovery" category.

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

You will then need to create a .env file. This file should contain an API key that you keep to yourself:

    api-key=THIS_IS_YOUR_KEY

A database is required to run this project. Create a database file called webmentions.db and use sqlite3 to enter it:

    sqlite3 webmentions.db

Use these commands to create the tables necessary to run this project:

    CREATE TABLE webmentions (
        source,
        target,
        property,
        contents,
        author_name,
        author_photo,
        author_url,
        content_html,
        received_date,
        status
    );

    CREATE TABLE sent_webmentions (
        source,
        target,
        sent_date,
        status_code,
        response
        webmention_endpoint
    );

After following these steps, you are ready to use the endpoint. To run the server, run this command:

    flask run

In accordance with the webmention specification, the webmention receiver processes webmentions asynchronously. I use cron to process webmentions every hour.

To process webmentions, you should set up a cron job that executes the validate_webmention.py script. An example cron job you could use is:

    0 * * * * python3 /path/to/webmention_receiver/validate_webmention.py

## Authentication

This application uses basic authentication in query parameters. To view the /home and /sent resources, you should append the following query string to the URL you want to access:

    ?key=api-key

api-key should be equal to the value of api-key that you set in your .env file.

## License

This project is licenced under the MIT License.
