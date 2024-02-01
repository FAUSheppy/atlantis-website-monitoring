import pika
import requests
import argparse
import checks
import json
import sys

MASTER_HOST = None
FILE_OVERWRITE = None

def callback(ch, method, properties, body):

    print(body)
    d = json.loads(body)

    url = d.get("url")
    recursive = d.get("recursive")

    full_ignore = d.get("spelling_full_ignore_words")
    extra_words = d.get("spelling_extra_words")

    check_lighthouse = d.get("check_lighthouse")
    check_links = d.get("check_links") or recursive
    check_spelling = d.get("check_spelling")
    
    if recursive:
        results = checks.check_recursive(url, check_lighthouse, check_links, check_spelling, extra_words)
    else:
        r, body = checks.check_url(url, check_lighthouse, check_links, check_spelling, extra_words, full_ignore)
        results = { "check" : { url : r } }

    # submitt results back to master #
    results.update({ "token" : d.get("token") })
    results.update({ "url" : url })

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

    if FILE_OVERWRITE:
        with open(FILE_OVERWRITE) as f:
            callback(None, None, None, f.read())
        sys.exit(0)

    # Establish connection to RabbitMQ server
    connection = pika.BlockingConnection(pika.ConnectionParameters(args.queue_host))
    channel = connection.channel()
    channel.queue_declare(queue='scheduled')
    channel.basic_consume(queue='scheduled', on_message_callback=callback, auto_ack=True)
    channel.start_consuming()
