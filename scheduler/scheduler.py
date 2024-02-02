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

    while(True):
        r = requests.get(args.master_host + "/get-check-info")
        for c in r.json():
            print(c)
            requests.get(args.master_host + "/schedule-check?url={}".format(c["base_url"]))

        time.sleep(int(args.sleep_time*60))
