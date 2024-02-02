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
import secrets
import uuid
from flask_wtf import CSRFProtect

import sqlalchemy
from sqlalchemy import Column, Integer, String, Boolean, or_, and_, asc, desc, not_, ForeignKey
from sqlalchemy.orm import relationship
from flask_sqlalchemy import SQLAlchemy

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField, DecimalField, HiddenField, SelectField
from wtforms.validators import DataRequired, Length, URL

app = flask.Flask("Atlantis Web-Checker")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///sqlite.db"
db = SQLAlchemy(app)

class EntryForm(FlaskForm):

    url = StringField("URL", validators=[URL()])
    uuid_hidden = HiddenField("service_hidden")
    recursive = BooleanField("recursive")

class DictionaryWord(db.Model):

    __tablename__ = "words"

    owner = Column(String, primary_key=True)
    word = Column(String, primary_key=True)
    full_ignore = Column(Boolean) # ignore this word or pattern completely


class URL(db.Model):

    __tablename__ = "url"

    uuid = Column(String, primary_key=True)

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

    def serialize(self):
        return {
            "uuid" : self.uuid,
            "base_url" : self.base_url,
            "owner" : self.owner,
            "check_spelling" : self.check_spelling,
            "check_lighthouse" : self.check_lighthouse,
            "check_links" : self.check_links,
            "recursive" : self.recursive,
            "master_host" : self.master_host,
            "disabled" : self.disabled,
        }


class CheckResult(db.Model):

    __tablename__ = "results"

    uuid = Column(String, primary_key=True)
    parent = Column(String, ForeignKey("url.base_url"))

    url = Column(String)
    base_check = Column(String)
    timestamp = Column(String)

    lighthouse_score = Column(String)
    lighthouse_results = Column(String)

    links_results = Column(String)
    links_failed_count = Column(Integer)

    check_failed_message = Column(String)

@app.route("/get-check-info")
def get_check_info():
    '''Get info about checks for scheduler'''

    # get all URLs with no checks so far #
    no_check_results = db.session.query(URL).outerjoin(
                        CheckResult, URL.uuid==CheckResult.parent).filter(CheckResult.uuid==None).all()

    # get all URLs with outdated checks #
    run_before_base = datetime.datetime.now() - datetime.timedelta(minutes=5)
    outdated_joined = db.session.query(URL).join(CheckResult, URL.base_url == CheckResult.parent)
    outdated_results = outdated_joined.filter(
                and_(CheckResult.timestamp < run_before_base.isoformat(), CheckResult.timestamp != None)).all()

    # updated outdated checks with extended #
    run_before_extended = datetime.datetime.now() - datetime.timedelta(hours=23)
    all_list = db.session.query(URL).filter().all()
    all_list = db.session.query(URL).join(CheckResult, URL.base_url == CheckResult.parent).all()
    for url_obj in all_list:
        timestamp = datetime.datetime.fromisoformat(url_obj.timestamp)
        if timestamp > run_before_extended:

            # find in list by uuid
            target_obj_index = outdated_results.index(url.uuid)

            # set exteneded check to false in the outdated list #
            outdated_results[target_obj_index].check_links = False
            outdated_results[target_obj_index].check_lighthouse = False
            outdated_results[target_obj_index].check_spelling = False

    # combine & return results #
    combined_list = [ r.serialize() for r in no_check_results + outdated_results]
    return flask.jsonify(combined_list)

@app.route("/submit-check", methods=["POST"])
def submit_check():
    '''Receive a json dict of url : check_results from a worker'''

    jdict = flask.request.json
    url_obj = db.session.query(URL).filter(URL.base_url==jdict["url"]).first()

    print(json.dumps(jdict, indent=2))

    if not "token" in jdict or url_obj.token != jdict.get("token"):
        return ("Missing or wrong token in submission", 401)

    for url, results, in jdict["check"].items():

        check_failed_message = ""

        # base information #
        check_result_obj = CheckResult()
        check_result_obj.uuid = str(uuid.uuid4())
        check_result_obj.url = url
        check_result_obj.parent = url_obj.uuid
        check_result_obj.timestamp = datetime.datetime.now().isoformat()

        # base check #
        check_result_obj.base_check = results["base_status"]
        if not check_result_obj.base_check:
            check_failed_message += "ERROR: URL unreachable:\n{}\n".format(check_result_obj.url)

        if "lighthouse" in results:
            check_result_obj.lighthouse_audits = results.get("lighthouse").get("results")
            check_result_obj.lighthouse_score = results.get("lighthouse").get("score")

            # lighthouse problem #
            if check_result_obj.lighthouse_score < 0.75:
                check_failed_message += "Warning: Lighthouse score degraded\n{}\n".format(check_result_obj.url)

        if "links" in results:
            check_result_obj.links_failed_count = results.get("links")["failed"]
            check_result_obj.links_results = results.get("links")["results"]

            # dead links problem #
            if check_result_obj.links_results > 0:
                check_failed_message += "Warning: Dead Links on Website ->\n"
                check_failed_message += "\n".join(check_result_obj.links_results)

        # overall fail ? #
        check_result_obj.base_check = bool(check_failed_message)
        check_result_obj.check_failed_message = check_failed_message

        # add and commit #
        db.session.add(check_result_obj)
        db.session.commit()

        # try to get last #
        last_q = db.session.query(CheckResult).filter(
                    and_(CheckResult.parent==URL.uuid, CheckResult.url==jdict["url"], not_(CheckResult.uuid==check_result_obj.uuid)))
        last = last_q.first()

        # dispatch configured, and based check failed + either no last result or last result success #
        if(((not last and not check_result_obj.base_check)
                or (last and last.base_check != check_result_obj.base_check))
                and app.config.get("DISPATCH_SERVER")):
            payload = { "users": [target_user], "msg" : message }
            r = requests.post(app.config["DISPATCH_SERVER"] + "/smart-send",
                                 json=payload, auth=app.config["DISPATCH_AUTH"])

        return "OK"

@app.route("/schedule-check")
def schedule_check():

    user = flask.request.headers.get("X-Forwarded-Preferred-Username") or "anonymous"
    url = flask.request.args.get("url")

    if not url:
        return ("Missing URL", 405)

    url_obj = db.session.query(URL).filter(and_(URL.owner==user, URL.base_url==url)).first()

    if not url_obj:
        return ("Combination of {} and {} does not exist".format(url, user), 404)

    push_dict = {
        "url" : url_obj.base_url,
        "spelling_full_ignore_words" : "",
        "spelling_extra_words" : "",
        "check_spelling" : url_obj.check_spelling,
        "check_lighthouse" : url_obj.check_lighthouse,
        "check_links"  : url_obj.check_links,
        "recursive" : url_obj.recursive,
        "token" : url_obj.token,
    }

    connection = pika.BlockingConnection(pika.ConnectionParameters(app.config["QUEUE_SERVER"]))
    channel = connection.channel()
    channel.queue_declare(queue='scheduled')
    channel.basic_publish(exchange='', routing_key='scheduled', body=json.dumps(push_dict))
    connection.close()

    return "OK"

def create_modify_entry(form, user):

    token = secrets.token_urlsafe(16)

    print(form.url.__dict__)
    url = form.url.data
    uuid_hidden = form.uuid_hidden.data or str(uuid.uuid4())

    if not uuid_hidden or not url:
        raise AssertionError("Missing URL [{}] or uuid_hidden [{}] - oO?".format(url, uuid_hidden))

    # keep token if modification #
    s_tmp = db.session.query(URL).filter(URL.uuid==uuid_hidden).first()
    url_obj = URL(uuid=uuid_hidden, base_url=url, owner=user, token=token, recursive=form.recursive.data)

    db.session.merge(url_obj)
    db.session.commit() 

@app.route("/check-details")
def check_details():

    user = flask.request.headers.get("X-Forwarded-Preferred-Username") or "anonymous"
    url = flask.request.args.get("url")

    if not url:
        return ("Missing '?url=...' argument", 404)

    # check url #
    url_obj = db.session.query(URL).filter(and_(URL.owner==user, URL.base_url==url)).first()
    if not url_obj:
        return ("Combination of {} and {} does not exist".format(url, user), 404)

    return flask.render_template("service_info.html", url_check_obj=url_obj)

@app.route("/create-modify", methods=["GET", "POST", "DELETE"])
def form_endpoint():

    user = flask.request.headers.get("X-Forwarded-Preferred-Username") or "anonymous"
    url = flask.request.args.get("url")
    url_obj = del_object = db.session.query(URL).filter(and_(URL.base_url==url, URL.owner==user)).first()

    # check if is delete #
    operation = flask.request.args.get("operation")
    if operation and operation == "delete" :

        if not url_obj:
            return ("Failed to delete the requested service", 404)

        db.session.delete(url_obj)
        db.session.commit()

        return flask.redirect("/")

    form = EntryForm()

    # handle modification #
    if url_obj: # TODO fix this use UUID for mod not URL (create double)
        form.url.default = url_obj.base_url
        form.recursive.default = url_obj.recursive
        form.uuid_hidden.default = url_obj.uuid
        form.process()
    elif url:
        return ("Not a valid service to modify", 404)

    if flask.request.method == "POST":
        if form.validate():
            create_modify_entry(form, user)
            service_name = form.url.data
            return flask.redirect('/check-details?url={}'.format(service_name))
        else:
            print(form.url.data)
            return flask.render_template('add_modify_form.html', form=form)
    else:
        return flask.render_template('add_modify_form.html', form=form)

@app.route("/")
@app.route("/overview")
def index():

    user = flask.request.headers.get("X-Forwarded-Preferred-Username") or "anonymous"
    url_checks = db.session.query(URL).filter(URL.owner==user).all()
    return flask.render_template("overview.html", user=user, config=app.config, url_checks=url_checks)

def create_app():

    # prepare database #
    db.create_all()

    # set dispatch server info #
    app.config["DISPATCH_SERVER"] = os.environ.get("DISPATCH_SERVER")
    if not app.config["DISPATCH_SERVER"]:
        print("Warning: env:DISPATCH_SERVER not configured!", file=sys.stderr)
    else:
        app.config["DISPATCH_AUTH"] = (os.environ["DISPATCH_AUTH_USER"], os.environ["DISPATCH_AUTH_PASSWORD"])

    # set rabbitmq connection #
    app.config["QUEUE_SERVER"] = os.environ.get("QUEUE_SERVER")

    # check pika connection #
    test_c = pika.BlockingConnection(pika.ConnectionParameters(app.config["QUEUE_SERVER"]))
    assert(test_c.is_open)
    test_c.close()

    # set secret for CSRF #
    app.config["SECRET_KEY"] = secrets.token_urlsafe(64)

    #csrf = CSRFProtect()
    #csrf.init_app(app)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Website Monitoring Service',
                        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    # general parameters #
    parser.add_argument("-i", "--interface", default="127.0.0.1", help="Interface to listen on")
    parser.add_argument("-p", "--port",      default="5000",      help="Port to listen on")
    parser.add_argument("-q", "--queue",     default="localhost", help="Pika queue target")

    args = parser.parse_args()
    os.environ["QUEUE_SERVER"] = args.queue

    with app.app_context():
        create_app()

    app.run(host=args.interface, port=args.port, debug=True)
