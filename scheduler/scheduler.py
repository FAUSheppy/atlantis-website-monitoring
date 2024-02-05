import os
import json
import sys
import requests
import time
import argparse

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Website Monitoring Scheduler',
                        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("-H", "--master-host", default="http://localhost:5000", help="Master Server to schedule")
    parser.add_argument("-s", "--sleep-time", type=float, default=5, help="Run every x-minutes")
    args = parser.parse_args()

    master_host = args.master_host
    if os.environ.get("MASTER_HOST"):
        master_host = os.environ.get("MASTER_HOST")

    # default to http if scheme is missing #
    if not master_host.startswith(("https://", "http://")):
        master_host = "http://" + master_host

    sleep_time = args.sleep_time
    if os.environ.get("SLEEP_TIME"):
        sleep_time = float(os.environ.get("SLEEP_TIME"))

    while(True):

        try:
            r = requests.get(master_host + "/get-check-info")
            print(r.content)
            for c in r.json():
                print(c)
                requests.post(master_host + "/schedule-check?url={}".format(c["base_url"]), json=c)
        except requests.exceptions.ConnectionError as e:
            print(e)

        time.sleep(int(sleep_time*60))
