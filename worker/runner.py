import pika
import argparse
import checks
import json

MASTER_HOST = None
TOKEN = None

def callback(ch, method, properties, body):

    d = json.loads(body)

    url = d.get("url")
    recursive = d.get("url")

    check_lighthouse = d.get("check_lighthouse")
    check_links = d.get("check_links") or recursive
    check_spelling = d.get("check_spelling")
    
    if recursive:
        results = checks.check_recursive(url, check_lighthouse, check_links, check_spelling)
    else:
        results = checks.check_url(url, check_lighthouse, check_links, check_spelling)

    for r in results:
        r.update({ "token" : TOKEN })
        requests.post("{}{}".format(MASTER_HOST, "/submit-check"), json=r)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Website Monitoring Runner',
                        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("-h", "--master-host", default="main", help="Master Server to submit results to")
    parser.add_argument("-h", "--queue-host", default="queue", help="Queue host to subscribe to")
    parser.add_argument("-q", "--queue", default="scheduled", help="Queue to consume")
    parser.add_argument("-t", "--work-submission-token", required=True, help="Main Server Submission Username")

    args = parser.parse_args()

    MASTER_HOST = args.master_host
    TOKEN = args.work_submission_token

    # Establish connection to RabbitMQ server
    connection = pika.BlockingConnection(pika.ConnectionParameters(args.queue_host))
    channel = connection.channel()
    channel.queue_declare(queue='scheduled')
    channel.basic_consume(queue='scheduled', on_message_callback=callback, auto_ack=True)
    channel.start_consuming()
