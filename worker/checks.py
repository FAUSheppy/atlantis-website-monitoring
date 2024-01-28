from lighthouse import LighthouseRunner
import urllib.parse
import requests
import bs4

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


def _put_urls_for_body(body, urls_todo, urls_queued, current_url):
    '''Update the link queue with new links from a give body of HTML'''

    # parse body and get hrefs #
    soup = bs4.BeautifulSoup(response.text, 'html.parser')
    links = soup.find_all('a')
    link_list = [link.get('href') for link in links]

    for l in link_list:

        # check if internal URL #
        link_parsed = urllib.parse.urlsparse(l)
        cur_url_parsed = urllib.parse.urlsparse(current_url)
        if not link_parsed.netloc and link_parsed.netloc != cur_url_parsed.netloc:
            continue

        # check if url is already queued #
        if l in urls_queued:
            continue
        else:
            # queue and mark queued #
            urls_queued.update({link:True})
            urls_todo.put(l)

def check_url_recursive(url, check_lighthouse, check_links, check_spelling):

    results = []
    urls_queued = dict()
    urls_todo = queue.Queue()
    urls_todo.put(url)

    while not urls_todo.empty():

        result, body = check_url(urls_todo.get(), check_lighthouse, check_links, check_spelling)
        results.append(result)
        _put_urls_for_body(body, urls_todo, urls_queued, current_url=url)

    return result

def check_url(url, check_lighthouse, check_links, check_spelling, external_only=False):

    result = dict()

    status, body = check_website_reachable(url)
    result_dict.update({"base_status" : status })

    if check_lighthouse:
        result.update({"lighthouse" : check_lighthouse(url)})
    if check_spelling:
        result.update({"spelling" : check_spelling(url)})
    if check_links:
        result.update({"links" : check_links(url, external_only)})

    return (result, body)
