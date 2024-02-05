import pika
import json
import requests
import argparse
import checks
import json
import sys
import datetime
import os
import time

MASTER_HOST = None
FILE_OVERWRITE = None

recent_events = {}
purge_cycle_next = None

def _is_recent_duplicate(body):

    global purge_cycle_next
    global recent_events

    if not purge_cycle_next or purge_cycle_next < datetime.datetime.now():
        purge_cycle_next = datetime.datetime.now() + datetime.timedelta(minutes=5)
        recent_events = {}

    if hash(body) in recent_events:
        return True
    else:
        recent_events.update({ hash(body) : datetime.datetime.now() })
        return False

def callback(ch, method, properties, body):

    print(body)
    d = json.loads(body)

    if not d.get("force_run") and _is_recent_duplicate(body):
        print("Skipping.. (duplicate)")
        return

    url = d.get("url")
    recursive = d.get("recursive")

    full_ignore = d.get("spelling_full_ignore_words")
    extra_words = d.get("spelling_extra_words")

    check_lighthouse = d.get("check_lighthouse")
    check_links = d.get("check_links") or recursive
    check_spelling = d.get("check_spelling")
    
    if recursive:
        results = checks.check_url_recursive(url, check_lighthouse, check_links,
                                                check_spelling, extra_words)
    else:
        r, body = checks.check_url(url, check_lighthouse, check_links,
                                    check_spelling, extra_words, full_ignore)
        results = { "check" : [(url,r)] }

    # submitt results back to master #
    results.update({ "token" : d.get("token") })
    results.update({ "url" : url })

    print(json.dumps(results, indent=2))
    r = requests.post("{}{}".format(MASTER_HOST, "/submit-check"), json=results)
    print(r.status_code, r.content)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Website Monitoring Runner',
                        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("-H", "--master-host", default="main", help="Master Server to submit results to")
    parser.add_argument("-q", "--queue-host", default="queue", help="Queue host to subscribe to")
    parser.add_argument("-n", "--queue-name", default="scheduled", help="Queue to consume")
    parser.add_argument("-f", "--file-overwrite", help="Read and write to file instead")

    args = parser.parse_args()

    MASTER_HOST = args.master_host
    FILE_OVERWRITE = args.file_overwrite

    queue_host = args.queue_host
    queue_name = args.queue_name

    if os.environ.get("MASTER_HOST"):
        MASTER_HOST = os.environ.get("MASTER_HOST")
    if os.environ.get("QUEUE_HOST"):
        queue_host = os.environ.get("QUEUE_HOST")
    if os.environ.get("QUEUE_NAME"):
        queue_name = os.environ.get("QUEUE_NAME")

    if not MASTER_HOST.startswith(("https://", "http://")):
        MASTER_HOST = "http://" + MASTER_HOST


    if FILE_OVERWRITE:
        with open(FILE_OVERWRITE) as f:
            callback(None, None, None, f.read())
        sys.exit(0)

    # Establish connection to RabbitMQ server
    for i in range(0,5):

        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(queue_host))
            print("Connected successfully to {}".format(queue_host))
            channel = connection.channel()
            channel.queue_declare(queue=queue_name)
            channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as e:
            print(type(e), file=sys.stderr)

        # increasing backoff time #
        print("Retrying in... {}s".format(i*20), file=sys.stderr)
        time.sleep(i*60)
