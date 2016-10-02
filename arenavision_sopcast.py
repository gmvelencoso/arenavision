#!/home/gerard/dev/arenavision/.venv/bin/python

import requests
from time import sleep
from datetime import datetime, timedelta
from tabulate import tabulate
from lxml import html
import subprocess
import re
import sys
import argparse

BASE_URL = "http://arenavision.in/"

SOP_PORT = "8908"

HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'es,ca;q=0.8,en-US;q=0.6,en;q=0.4,:max-age=0',
    'Host': 'arenavision.in',
    'Referer': 'http://arenavision.in/',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.75 Safari/537.36'
}

DATEFORMAT = "%d/%m/%Y %H:%M"

CHAN_EXP = "/(AV[0-9]{1,2})"
SPORT_EXP = "CET ([^:]+):"
DESC_EXP = "CET {sport}: (.*)/{join_channels}"

HAS_SOPCAST = False
HAS_ACESTREAM = False

class Item(object):
    def __init__(self, data):
        self.time, self.sport, self.match, self.category, self.channels = data        
        self.soplinks = []
    
    def __str__(self):
        return str((self.time, self.sport, self.match, self.category, self.channels, self.soplinks))

    def gettime(self):
        return self.time.strftime(DATEFORMAT)

    def header(self):
        return "\n".join([self.sport + " - " + self.category, self.gettime() + " " + self.match])

    def tolist(self):
        return [
            self.gettime(),
            self.sport.decode("utf8"),
            self.category.decode("utf8"),
            self.match.decode("utf8")
        ]

    def matches(self, keywords):
        haystack = str(self).lower()
        return any(keyword for keyword in keywords if keyword in haystack)


def get_page(url):
    try:
        req = requests.get(url, headers=HEADERS)
        return req.content
    except requests.exceptions.ConnectionError:
        print "Could not connect with host. Please retry later. Sorry."
        raise KeyboardInterrupt


def clean_page(content):
    return content.replace("<br />", "").replace("<br>", "").replace("\t", "").replace("\n", " ")


def parse_schedule_row_node(row):
    try:        
        rdate, rtime, rsport, rcat, rmatch, channels = map(lambda x: x.text.strip(), row)
        if rdate and rtime:
            time = datetime.strptime(rdate + " " + rtime.replace(" CET", ""), DATEFORMAT)
            
            available_channels = re.findall("(S?[0-9]+)", channels)

            if not HAS_SOPCAST:
                available_channels = [x for x in available_channels if "S" not in x]

            if not HAS_ACESTREAM:
                available_channels = [x for x in available_channels if not x.isdigit()]
            
            if available_channels:
                return time, rsport, rmatch, rcat, sorted(available_channels)
    except Exception as e:
        print e
    return None


def get_schedule():
    page = get_page(BASE_URL + "agenda")
    tree = html.fromstring(clean_page(page))
    items = []
    for match in tree.xpath('//table//tr[td/@class="auto-style3"]'):
        data = parse_schedule_row_node(match)
        if data:
            item = Item(data)
            items.append(item)    
    return items


def crawl_sopcast_links(item):
    for chan in item.channels:
        page = get_page(BASE_URL + "av" + chan.lower())
        tree = html.fromstring(page)
        link = tree.xpath("//a[contains(@href, 'sop://')]/@href")
        if link:
            item.soplinks.append(link[0])


def clear_screen():
    sys.stdout.write("\033[2J\033[;H")


def print_buffering(value):
    sys.stdout.write("\rBuffering... {0}%".format(value))


def show_match_options(match):

    choose = "Choose a sopcast channel to start streaming"

    option = option_chooser(header=match.header(), choose=choose, options=[[link,] for link in match.soplinks])

    start_streaming(match.soplinks[option])
    

def start_streaming(soplink):
    print "Start streaming channel: " + soplink

    vlcrunning = False
    sopprocess = None

    try:
        sopcmd = ["sp-sc-auth", soplink, "3908", SOP_PORT]
        vlccmd = ["cvlc", "http://localhost:" + SOP_PORT + "/tv.asf"]

        sopprocess = subprocess.Popen(sopcmd, stdout=subprocess.PIPE)
        
        print "Wating for stream to buffer"
        print_buffering(0)
        
        while True:
            line = sopprocess.stdout.readline()
            if "nblockAvailable" in line:
                buff = line.split("nblockAvailable=")[-1]
                print_buffering(buff.strip())
                if not vlcrunning and int(buff) > 30:
                    subprocess.Popen(vlccmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    vlcrunning = True
        sopprocess.terminate()
        print "Bye!"
    except KeyboardInterrupt, e:
        print "\nStop stream. Exit."
        sopprocess.terminate()
        raise


def main(args):
    print "Requesting schedules from {0}".format(BASE_URL + "agenda")
    items = get_schedule()

    # we want to filter matches already finished (past) or too late to start streaming (future)
    past = datetime.now() - timedelta(hours=2)
    future = datetime.now() + timedelta(hours=24)
    items = filter(lambda x: past < x.time < future, items)
    items = sorted(items, key=lambda x: x.time, reverse=False)

    if args:
        # args cannot be a generator, as it will loop each item, and will be consumed on first Item.matches call
        args = [arg.lower() for arg in args]
        items = [item for item in items if item.matches(args)]

    if not items:
        print "No matches found. Exit."
        return 1

    match = None

    while not match:
        if len(items) == 1:
            match = items[0]
            print "Only one match: {0}".format(" ".join(match.tolist()).encode("utf-8"))
            sleep(3)
            break

        choose_string = "Choose a channel or type a sport to filter"

        items_list = [item.tolist() for item in items]
        input = option_chooser(options=items_list, choose=choose_string, allowfilter=True)
        if type(input) is int:
            match = items[input]
        else:
            # this is a keyword to filter
            filtered = [item for item in items if item.matches((input.lower(),))]
            if not filtered:
                print "No results to show, please check your filter"
                sleep(2)
            else:
                items = filtered

    crawl_sopcast_links(match)
    show_match_options(match)
    return 0


def get_indexed_options(items, start=0):
    """
    returns a enumerated index to item (list) itself
    """
    result = []
    for i, item in enumerate(items, start=start):
        assert type(item) is list
        result.append([i] + item)
    return result


def parse_arguments(args):
    parser = argparse.ArgumentParser(description='Searchs for sports events in http://arenavision.in and starts a sopcast stream')
    parser.add_argument('filter', nargs='*', help='Word to start filtering the results')
    return parser.parse_args(args)


def startup():
    # TODO: check if vlc is available
    # TODO: check if sp-sc-auth or acestreamengine or both are available
    global HAS_SOPCAST, HAS_ACESTREAM
    HAS_SOPCAST = True
    HAS_ACESTREAM = False

def option_chooser(header="", options=None, choose="Enter a number", allowfilter=False):
    """
    asks for a user input (index) based on a list. 0 for exit.
    Returns a options item index or a filter string if enabled
    """
    input = None

    if not options:
        print "No possible options to show."
        raise KeyboardInterrupt()

    # appends the index to the first element of each option
    options = get_indexed_options(options, start=1)

    while not input:
        clear_screen()
        if header:
            print header

        print tabulate(options)

        input = raw_input(choose + " (0 to exit): ")
        # TODO: externalise logic
        if not input.isdigit():
            if allowfilter:
                return input
            else:
                print "Type a valid item index: "
                input = None
                sleep(3)
        else:
            if input == "0":
                raise KeyboardInterrupt()

            try:
                _ = options[int(input) - 1]  # enumerate starts in 1
                # as its a valid index, let's return it:
                return int(input) - 1
            except IndexError as ie:
                print "Type a valid index channel"
                input = None
                sleep(2)
    return input


if __name__ == "__main__":
    try:
        startup()
        args = parse_arguments(sys.argv[1:])
        exit(main(args.filter))
    except KeyboardInterrupt as e:
        print "Good bye!"

