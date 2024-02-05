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
import time
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
    recursive = BooleanField("Recursive Check")

    check_links = BooleanField("Check Links")
    check_lighthouse = BooleanField("Check Performance")
    check_spelling = BooleanField("Check Spelling")

    master_host = StringField("Group")

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

    results = relationship("CheckResult", uselist=True)

    def __eq__(self, other):
        if isinstance(other, str):
            return self.uuid == other
        return self.uuid == other.uuid

    def last_result(self):

        last_query = db.session.query(CheckResult).filter(CheckResult.parent==self.uuid)
        last = last_query.order_by(CheckResult.timestamp.desc()).first()

        return last

    def last_human_date(self):
        '''Get the last timestamp for an URL'''

        last = self.last_result()
        if last:
            dt = datetime.datetime.fromtimestamp(last.timestamp)
            return dt.strftime("%d. %B %Y at %H:%M")
        else:
            return "No Check for this URL"

    def last_status(self):

        last = self.last_result()
        if last:
            if last.base_check == True:
                if last.check_failed_message:
                    return "WARNING"
                else:
                    return "OK"
            else:
                return "ERROR"
        else:
            return "UKNOWN"

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
    parent = Column(String, ForeignKey("url.uuid"))

    url = Column(String)
    base_check = Column(Boolean)
    timestamp = Column(Integer)

    lighthouse_score = Column(Integer)
    lighthouse_results = Column(String)

    links_results = Column(String)
    links_failed_count = Column(Integer)

    spelling = Column(String)
    spelling_failed_count = Column(Integer)

    check_failed_message = Column(String)

@app.route("/get-check-info")
def get_check_info():
    '''Get info about checks for scheduler'''

    # get all URLs with no checks so far #
    no_check_results = db.session.query(URL).outerjoin(
                CheckResult, URL.uuid==CheckResult.parent).filter(CheckResult.uuid==None).all()

    # get all URLs with outdated checks #
    run_before_base = datetime.datetime.now() - datetime.timedelta(minutes=5)
    outdated_joined = db.session.query(URL).join(CheckResult, URL.uuid == CheckResult.parent)
    outdated_results = outdated_joined.filter(
            and_(CheckResult.timestamp < run_before_base.timestamp(),
                 CheckResult.timestamp != None)).all()

    # updated outdated checks with extended #
    run_before_extended = datetime.datetime.now() - datetime.timedelta(hours=5)
    not_outdated_extended = db.session.query(URL).join(CheckResult, URL.uuid == CheckResult.parent).filter(
            and_(CheckResult.timestamp > run_before_extended.timestamp(), CheckResult.timestamp != None),
                 or_(CheckResult.spelling.isnot(None),
                     CheckResult.links_results.isnot(None),
                     CheckResult.lighthouse_score.isnot(None))
            ).all()

    for url_obj in not_outdated_extended:

        print(url_obj.base_url, "removing advanced checks", file=sys.stderr)

        try:
            # find in list by uuid
            target_obj_index = outdated_results.index(url_obj.uuid)
        except ValueError:
            continue

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

    for url, results in jdict["check"]:

        check_failed_message = ""

        # base information #
        check_result_obj = CheckResult()
        check_result_obj.uuid = str(uuid.uuid4())
        check_result_obj.url = url
        check_result_obj.parent = url_obj.uuid
        check_result_obj.timestamp = datetime.datetime.now().timestamp()

        # base check #
        check_result_obj.base_check = bool(results["base_status"])
        if not check_result_obj.base_check:
            check_failed_message += "ERROR: URL unreachable:\n{}\n".format(check_result_obj.url)

        if "spelling" in results:
            check_result_obj.spelling = json.dumps(results.get("spelling"))
            check_result_obj.spelling_failed_count = len(results.get("spelling"))

        if "lighthouse" in results:
            check_result_obj.lighthouse_audits = results.get("lighthouse").get("results")
            check_result_obj.lighthouse_score = results.get("lighthouse").get("score").get("performance")

            # lighthouse problem #
            if check_result_obj.lighthouse_score < 0.75:
                check_failed_message += "Warning: Lighthouse score degraded\n{}\n".format(
                    check_result_obj.url)

        if "links" in results:
            check_result_obj.links_failed_count = results["links"]["failed"]
            check_result_obj.links_results = json.dumps(results["links"]["results"])

            # dead links problem #
            if check_result_obj.links_failed_count > 0:
                check_failed_message += "Warning: Dead Links on Website ->\n"
                failed_links = [ list(el.keys())[0] for el in results["links"]["results"]
                                         if not list(el.values())[0] ]
                check_failed_message += "\n".join(failed_links)

        # overall fail ? #
        # check = False (fail) if message is non-empty #
        check_result_obj.base_check = not bool(check_failed_message)
        check_result_obj.check_failed_message = check_failed_message

        # add and commit #
        db.session.add(check_result_obj)
        db.session.commit()

        # try to get last #
        last_q = db.session.query(CheckResult).filter(
                    and_(CheckResult.parent==URL.uuid,
                         CheckResult.url==jdict["url"],
                         not_(CheckResult.uuid==check_result_obj.uuid))).order_by(CheckResult.timestamp.desc())

        last = last_q.first()

        # dispatch configured and based check failed + either no last result or last was success #
        if((not last and not check_result_obj.base_check)
                or (last and last.base_check != check_result_obj.base_check)):

            if check_result_obj.base_check:
                # build recovery message payload #
                payload = { "users": [url_obj.owner], "msg" : "{} recovered".format(check_result_obj.url) }
            else:
                # build error message payload #
                payload = { "users": [url_obj.owner], "msg" :
                                "{}\n{}".format(check_result_obj.url, check_failed_message) }

            # send dispatch #
            if app.config.get("DISPATCH_SERVER"):
                r = requests.post(app.config["DISPATCH_SERVER"] + "/smart-send",
                                 json=payload, auth=app.config["DISPATCH_AUTH"])
            else:
                # dummy message if dispatch would have fired #
                print("Dispatch would have fired (not configured) \n{}".format(json.dumps(payload, indent=2)))

        return "OK"

@app.route("/schedule-check", methods=["POST"])
def schedule_check():

    user = flask.request.json.get("owner") or "anonymous"
    print(user)
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

    # force run #
    if flask.request.args.get("force-run") == "1" or flask.request.json.get("force-run"):
        push_dict.update({ "force_run" : True })

    # overwrite from request #
    for info in ["check_spelling", "check_lighthouse", "check_links"]:
        if info in flask.request.json:
            push_dict.update({ info : flask.request.json[info] })

    connection = pika.BlockingConnection(pika.ConnectionParameters(app.config["QUEUE_HOST"]))
    channel = connection.channel()
    channel.queue_declare(queue='scheduled')
    print(push_dict)
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
    url_obj = URL(uuid=uuid_hidden, base_url=url, owner=user,
                    token=token, recursive=form.recursive.data,
                    check_links=form.check_links.data,
                    check_lighthouse=form.check_lighthouse.data,
                    check_spelling=form.check_spelling.data,
                    master_host=form.master_host.data)

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
    url_obj = del_object = db.session.query(URL).filter(
                    and_(URL.base_url==url, URL.owner==user)).first()

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
        form.check_links.default = url_obj.check_links
        form.check_lighthouse.default = url_obj.check_lighthouse
        form.check_spelling.default = url_obj.check_spelling
        form.master_host.default = url_obj.master_host
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
            return flask.render_template('add_modify_form.html', form=form)
    else:
        return flask.render_template('add_modify_form.html', form=form, is_modification=bool(url))

@app.route("/")
@app.route("/overview")
def index():

    user = flask.request.headers.get("X-Forwarded-Preferred-Username") or "anonymous"
    url_checks = db.session.query(URL).filter(URL.owner==user).all()
    return flask.render_template("overview.html", user=user, config=app.config,
                url_checks=url_checks)

def create_app():

    # prepare database #
    db.create_all()

    # set dispatch server info #
    app.config["DISPATCH_SERVER"] = os.environ.get("DISPATCH_SERVER")
    if not app.config["DISPATCH_SERVER"]:
        print("Warning: env:DISPATCH_SERVER not configured!", file=sys.stderr)
    else:
        app.config["DISPATCH_AUTH"] = (os.environ["DISPATCH_AUTH_USER"],
                                       os.environ["DISPATCH_AUTH_PASSWORD"])

    # set rabbitmq connection #
    app.config["QUEUE_HOST"] = os.environ.get("QUEUE_HOST")

    # check pika connection #
    for i in range(0,5):
        try:
            test_c = pika.BlockingConnection(pika.ConnectionParameters(app.config["QUEUE_HOST"]))
            test_c.close()
            break
        except pika.exceptions.AMQPConnectionError as e:
            print(e, file=sys.stderr)

        print("Retrying in... {}s".format(i*60))
        time.sleep(i*20)

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
    os.environ["QUEUE_HOST"] = args.queue

    with app.app_context():
        create_app()

    app.run(host=args.interface, port=args.port, debug=True)
