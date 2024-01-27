from lighthouse import LighthouseRunner

def check_website_reachable(url):

    r = requests.get(url)

def lighthouse(url):

    TIMINGS = [
        'speed-index'
    ]
    report = LighthouseRunner(url, form_factor='desktop', quiet=False, timings=TIMINGS).report
    print(report.audits(0.5)['performance'].failed)

def check_spelling(url):

    r = requests.get(url)
    dictionary_path = pkg_resources.resource_filename("symspellpy", "frequency_dictionary_en_82_765.txt")
    bigram_path = pkg_resources.resource_filename("symspellpy", "frequency_bigramdictionary_en_243_342.txt")

    re

def check():

    check_website_reachable(url)
    check_lighthouse(url)
    check_spelling(url)
