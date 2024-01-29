from lighthouse import LighthouseRunner
import time
import queue
import re
import pkg_resources
import urllib.parse
import symspellpy
import requests
import bs4
import dateutil.parser

DEFAULT_FREQUENCY = 100

def _clean_whitespaces(text):

    # collapse #
    ret = re.sub(r'\s+', ' ', text)

    # remove leading #
    ret = re.sub(r'^\s', '', ret)

    # remove tailing
    ret = re.sub(r'\s$', '', ret)

    return ret

def check_website_reachable(url):

    r = requests.get(url)

    return (r.status_code, r.content)

def check_lighthouse_f(url):

    TIMINGS = [
        'speed-index'
    ]
    report = LighthouseRunner(url, form_factor='desktop', quiet=False, timings=TIMINGS).report
    print(report.audits(0.5)['performance'].failed)

def check_spelling_f(body, extra_words=[], full_ignore=[]):

    sym_spell = symspellpy.SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
    dictionary_path = pkg_resources.resource_filename("symspellpy", "frequency_dictionary_en_82_765.txt")
    bigram_path = pkg_resources.resource_filename("symspellpy", "frequency_bigramdictionary_en_243_342.txt")

    sym_spell.load_dictionary(dictionary_path, term_index=0, count_index=1)
    sym_spell.load_bigram_dictionary(bigram_path, term_index=0, count_index=2)

    for w in extra_words:
        sym_spell.create_dictionary_entry(w, DEFAULT_FREQUENCY)

    # get all texts from page #
    soup = bs4.BeautifulSoup(body, 'html.parser')
    texts = [ child.get_text() for child in soup.find_all() if isinstance(child.string, bs4.NavigableString) ]

    for t in texts:

        t_clean = _clean_whitespaces(t)

        # skip empty strings #
        if not t_clean:
            continue

        # skip dates #
        try:
            dateutil.parser.parse(t_clean, fuzzy=True)
            continue
        except dateutil.parser._parser.ParserError:
            pass

        suggestions = sym_spell.lookup_compound(t_clean, max_edit_distance=2, transfer_casing=True)

        print("===============================")
        print("'{}'".format(t_clean))
        for suggestion in suggestions:
            if(not suggestion.distance == 0 and
                not len(t_clean) <= 1):
                print(suggestion)

def check_links_f(url, body):

    results = []
    urls_queued = dict()
    urls_todo = queue.Queue()
    _put_urls_for_body(body, urls_todo, urls_queued, current_url=url)

    while not urls_todo.empty():
       
        cur = urls_todo.get()
        print(cur)
        time.sleep(1)
        result, body = check_url(cur, False, False, False)
        results.append({ cur: result["base_status"] in [301, 302, 200, 204] })

    return result

def _put_urls_for_body(body, urls_todo, urls_queued, current_url):
    '''Update the link queue with new links from a give body of HTML'''

    # parse body and get hrefs #
    soup = bs4.BeautifulSoup(body, 'html.parser')
    links = soup.find_all('a')
    link_list = [link.get('href') for link in links]

    for l in link_list:

        # check if internal URL #
        link_parsed = urllib.parse.urlparse(l)
        cur_url_parsed = urllib.parse.urlparse(current_url)
        if link_parsed.netloc and link_parsed.netloc != cur_url_parsed.netloc:
            continue

        # add base for pyrequests #
        if not link_parsed.netloc:
                l = "{}://{}{}".format(cur_url_parsed.scheme, cur_url_parsed.netloc, link_parsed.path)

        # check if url is already queued #
        if l in urls_queued:
            continue
        else:
            # queue and mark queued #
            urls_queued.update({l:True})
            urls_todo.put(l)

def check_url_recursive(url, check_lighthouse, check_links, check_spelling, extra_words=[], full_ignore=[]):

    results = []
    urls_queued = dict()
    urls_todo = queue.Queue()
    urls_todo.put(url)

    while not urls_todo.empty():

        result, body = check_url(urls_todo.get(), check_lighthouse, check_links, check_spelling,
                                    extra_words, full_ignore)
        results.append(result)
        _put_urls_for_body(body, urls_todo, urls_queued, current_url=url)

    return result

def check_url(url, check_lighthouse, check_links, check_spelling, external_only=False,
                extra_words=[], full_ignore=[]):

    result_dict = dict()

    status, body = check_website_reachable(url)
    result_dict.update({"base_status" : status })

    if check_lighthouse:
        result_dict.update({"lighthouse" : check_lighthouse_f(url)})
    if check_spelling:
        result_dict.update({"spelling" : check_spelling_f(body, extra_words, full_ignore)})
    if check_links:
        result_dict.update({"links" : check_links_f(url, body)})

    return (result_dict, body)
