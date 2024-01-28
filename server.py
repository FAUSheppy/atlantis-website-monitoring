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
import pika

import sqlalchemy
from sqlalchemy import Column, Integer, String, Boolean, or_, and_, asc, desc
from flask_sqlalchemy import SQLAlchemy

app = flask.Flask("Atlantis Web-Checker")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///sqlite.db"
db = SQLAlchemy(app)

class URL(db.Model):

    __tablename__ = "url"

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    base_url = Column(String)
    owner = Column(String)

    check_spelling = Column(Boolean)
    check_lighthouse = Column(Boolean)
    check_links = Column(Boolean)
    recursive = Column(Boolean)

    master_host = Column(String)

    settings = relationship("CheckResult", uselist=True)

class CheckResult(db.Model)

    __tablename__ = "results"

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    base_url = Column(String, ForeignKey("url.base_url"))

    url = Column(String)

    timstamp = Column(String)
    lighthouse = Column(String)
    base_check = Column(String)
    check_links = Column(String)

@app.route("/submit-check")
def submit_check():

    user = flask.request.headers.get("X-Forwarded-Preferred-Username")
    jdict = flask.request.json

    url_obj = db.session.query(URL).filter(owner=user, base_url=jdict.url).first()


    check_result_obj = CheckResult()

    check_result_obj.url = jdict.url
    check_result_obj.timstamp = datetime.datetime.now().isoformat()
    check_result_obj.lighthouse = jdict.lighthouse
    check_result_obj.base_check = jdict.base_check 
    check_result_obj.check_links = jdict.check_links

    db.session.add(check_result_obj)
    db.session.commit()

    return "OK"

@app.route("/schedule-check")
def schedule_check():

    user = flask.request.headers.get("X-Forwarded-Preferred-Username")
    url = flask.request.args.get("url")

    if not url:
        return ("Missing URL", 405)

    url_obj = db.session.query(URL).filter(owner=user, base_url=url).first()

    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='scheduled')
    channel.basic_publish(exchange='', routing_key='scheduled', body=url_obj.url)
    connection.close()

    return "OK"

@app.route("/")
def index():

    user = flask.request.headers.get("X-Forwarded-Preferred-Username")
    return flask.render_template("index.html", user=user, config=app.config)


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
