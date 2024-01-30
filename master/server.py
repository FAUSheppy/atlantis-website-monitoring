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

from wtforms import StringField, SubmitField, BooleanField, DecimalField, HiddenField, SelectField
from wtforms.validators import DataRequired, Length

app = flask.Flask("Atlantis Web-Checker")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///sqlite.db"
db = SQLAlchemy(app)

class EntryForm(FlaskForm):

    url = StringField("URL")
    uuid_hidden = HiddenField("service_hidden")
    recursive = BooleanField("recursive")

class DictionaryWord(db.Model):

    __tablename__ = "words"

    owner = Column(String, primary_key=True)
    word = Column(String, primary_key=True)
    full_ignore = Column(Boolean) # ignore this word or pattern completely


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

    # token to authenticate submission #
    token = Column(String)

    # disabled #
    disabled = Column(Boolean)

    settings = relationship("CheckResult", uselist=True)

    def human_date(self):
        dt = datetime.datetime.fromtimestamp(self.timestamp)
        return dt.strftime("%d. %B %Y at %H:%M")


class CheckResult(db.Model)

    __tablename__ = "results"

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    base_url = Column(String, ForeignKey("url.base_url"))

    url = Column(String)
    base_check = Column(String)
    timstamp = Column(String)

    lighthouse_score = Column(String)
    lighthouse_results = Column(String)

    links_results = Column(String)
    links_failed_count = Column(Integer)

@app.route("/submit-check")
def submit_check():
    '''Receive a json dict of url : check_results from a worker'''

    jdict = flask.request.json
    url_obj = db.session.query(URL).filter(owner=user, base_url=jdict["url"]).first()

    if not "token" in jdict or url_obj.token != jdict.get("token"):
        return ("Missing or wrong token in submission", 401)

    for key, value, in jdict.items():

        check_failed_message = ""

        # base information #
        check_result_obj = CheckResult()
        check_result_obj.url = jdict.get("url")
        check_result_obj.timstamp = datetime.datetime.now().isoformat()

        # base check #
        check_result_obj.base_check = jdict["base_status"]
        if check_result_obj.base_check:
            check_failed_message += "ERROR: URL unreachable:\n{}\n".format(check_result_obj.url)

        if "lighthouse" in value:
            check_result_obj.lighthouse_audits = value.get("lighthouse").get("results")
            check_result_obj.lighthouse_score = value.get("lighthouse").get("score")

            # lighthouse problem #
            if check_result_obj.lighthouse_score < 0.75:
                check_failed_message += "Warning: Lighthouse score degraded\n{}\n".format(check_result_obj.url)

        if "links" in value:
            check_result_obj.links_failed_count = jdict.get("links")["failed"]
            check_result_obj.links_results = jdict.get("links")["results"]

            # dead links problem #
            if check_result_obj.links_results > 0:
                check_failed_message += "Warning: Dead Links on Website ->\n"
                check_failed_message += "\n".join(check_result_obj.links_results)

        # overall fail ? #
        check_result_obj.failed = bool(check_failed_message)

        # add and commit #
        db.session.add(check_result_obj)
        db.session.commit()

        # try to get last #
        last_q = db.session.query(CheckResult).filter(owner=user, base_url=jdict.url, not_(uuid==url_obj.uuid))
        last = last_q.first()

        if not last.failed and check_result_obj.failed:
            payload = { "users": [target_user], "msg" : message }
            r = requests.post(app.config["DISPATCH_SERVER"] + "/smart-send",
                                 json=payload, auth=app.config["DISPATCH_AUTH"])

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

def create_modify_entry(form, user):

    token = secrets.token_urlsafe(16)

    url = form.url.data
    uuid = form.uuid_hidden.data or ""

    # keep token if modification #
    s_tmp = db.session.query(URL).filter(URL.uuid == uuid).first()
    if s_tmp:
        token = s_tmp.token
        if not token:
            raise AssertionError("WTF Service without Token {}".format(service_name))

    url_obj = URL(uuid=uuid, owner=user, token=token, recursive=form.recursive.data)

    db.session.merge(service)
    db.session.commit() 

@app.route("/create-modify", methods=["GET", "POST", "DELETE"])
def form_endpoint():

    user = flask.request.headers.get("X-Forwarded-Preferred-Username")

    # check if is delete #
    operation = flask.request.args.get("operation")
    if operation and operation == "delete" :

        uuid_delete = flask.request.args.get("uuid")
        del_object = db.session.query(URL).filter(URL.uuid==uuid_delete,
                                                Service.owner==user).first()

        if not del_object:
            return ("Failed to delete the requested service", 404)

        db.session.delete(service_del_object)
        db.session.commit()

        return flask.redirect("/")

    form = EntryForm()

    # handle modification #
    modify_uuid = flask.request.args.get("uuid")
    if modify_uuid:
        url_obj = db.session.query(URL).filter(URL.service == modify_uuid).first()
        if url_obj and url_obj.owner == user:
            form.url.default = url_obj.url
            form.recursive.default = url_obj.recursive
            form.uuid_hiddent.default = service.uuid
            form.process()
        else:
            return ("Not a valid service to modify", 404)

    if flask.request.method == "POST":
        create_modify_entry(form, user)
        service_name = form.url.data
        return flask.redirect('/service-details?service={}'.format(service_name))
    else:
        return flask.render_template('add_modify_service.html', form=form,
                    is_modification=bool(modify_service_name)

@app.route("/")
def index():

    user = flask.request.headers.get("X-Forwarded-Preferred-Username")
    url_checks = db.session.query(URL).filter(owner=user).all()
    return flask.render_template("overview.html", user=user, config=app.config, url_checks=url_checks)

def create_app():

    app.config["DISPATCH_SERVER"] = os.environ.get("DISPATCH_SERVER")
    app.config["DISPATCH_AUTH"] = (os.environ["DISPATCH_AUTH_USER"], os.environ["DISPATCH_AUTH_PASSWORD"])

    if not app.config["DISPATCH_SERVER"]:
        print("Warning: env:DISPATCH_SERVER not configured!", file=sys.stderr)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Website Monitoring Service',
                        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    # general parameters #
    parser.add_argument("-i", "--interface", default="127.0.0.1", help="Interface to listen on")
    parser.add_argument("-p", "--port",      default="5000",      help="Port to listen on")
    parser.add_argument("--dispatch-server", required=True,       help="Dispatche Server")

    with app.app_context():
        create_app()

    app.run(host=args.interface, port=args.port, debug=True)
