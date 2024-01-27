import hashlib                                                                                      
import os
import flask
import werkzeug
import requests
import argparse
import string
import sys
import json
import datetime

import sqlalchemy
from sqlalchemy import Column, Integer, String, Boolean, or_, and_, asc, desc
from flask_sqlalchemy import SQLAlchemy

app = flask.Flask("Atlantis Verfication")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///sqlite.db"
db = SQLAlchemy(app)

@app.route("/")
def index():
    # query configured ldap email + phone
    # query email + phone verification status
    # display as [ email ] [ example@atlantishq.com ] [ verified? ] [ verify now ]

    user = flask.request.headers.get("X-Forwarded-Preferred-Username")
    if not user:
        return ("X-Forwarded-Preferred-Username header is empty or does not exist", 500)
    verifications = ldaptools.get_verifications_for_user(user, app)
    if not verifications:
        return ("User object for this user not found.", 500)

    return flask.render_template("index.html", user=user, verifications=verifications,
                                    main_home=app.config["MAIN_HOME"])


def create_app():
    pass

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Website Monitoring Service',
                        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    # general parameters #
    parser.add_argument("-i", "--interface", default="127.0.0.1", help="Interface to listen on")
    parser.add_argument("-p", "--port",      default="5000",      help="Port to listen on")
    parser.add_argument("--dispatch-server", required=True,       help="Dispatche Server")
    app.run(host=args.interface, port=args.port, debug=True)
