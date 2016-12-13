#!/home/gerard/dev/arenavision/.venv/bin/python

import requests
from time import sleep
from datetime import datetime, timedelta
from tabulate import tabulate
from lxml import html
import subprocess
import re
import sys
import os
import argparse


BASE_URL = "http://arenavision.in/"
SCHEDULE_ENDPOINT = "schedule"

ACESTREAMENGINE = "/usr/bin/acestreamengine"
ACESTREAMPLAYER = "/usr/bin/acestreamplayer"

HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'es,ca;q=0.8,en-US;q=0.6,en;q=0.4,:max-age=0',
    'Host': 'arenavision.in',
    'Referer': BASE_URL,
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.75 Safari/537.36'
}

DATEFORMAT = "%d/%m/%Y %H:%M"

class Item(object):
    def __init__(self, data):
        self.time, self.sport, self.match, self.category, self.channels = data
        self.links = []

    def __str__(self):
        return str((self.time, self.sport, self.match, self.category, self.channels, self.links))

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

            channels = re.findall("([0-9]+)", channels)
            
            if channels:
                return time, rsport, rmatch, rcat, sorted(channels)
    except Exception as e:
        print e
    return None


def get_schedule():
    page = get_page(BASE_URL + SCHEDULE_ENDPOINT)
    tree = html.fromstring(clean_page(page))
    items = []
    for match in tree.xpath('//table//tr[td/@class="auto-style3"]'):
        data = parse_schedule_row_node(match)
        if data:
            item = Item(data)
            items.append(item)

    return items


def crawl_stream_links(item):
    for chan in item.channels:
        page = get_page(BASE_URL + "av" + chan.lower())
        tree = html.fromstring(page)

        link = tree.xpath("//a[contains(@href, 'acestream://')]/@href")
        if link:
            item.links.append(link[0])


def clear_screen():
    sys.stdout.write("\033[2J\033[;H")


def print_buffering(value):
    sys.stdout.write("\rBuffering... {0}%".format(value))


def show_match_options(match):

    choose = "Choose an acestream channel to start streaming"

    option = option_chooser(header=match.header(), choose=choose, options=[[link,] for link in match.links])

    start_streaming(match.links[option])


def start_process(command):
    return subprocess.Popen(command, stdout=open(os.devnull, 'w'), stderr=subprocess.STDOUT)


def start_streaming(link):
    engine = start_process([ACESTREAMENGINE, "--client-console"])
    player = start_process([ACESTREAMPLAYER, link])  # -f for fullscreen when stream starts

    print "Started acestream engine."
    print "Starting acestream player. To stop, close vlc window or press ctrl+c here"
    # wait until the user closes the vlc window
    try:
        player.communicate()
    except KeyboardInterrupt as e:
        player.terminate()
    finally:
        engine.terminate()

    
def start_streaming_obs(soplink):
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
    print "Requesting schedules from {0}".format(BASE_URL + SCHEDULE_ENDPOINT)
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

    crawl_stream_links(match)
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
    parser = argparse.ArgumentParser(description='Searchs for sports events in http://arenavision.in and starts acestream engine and player to view stream')
    parser.add_argument('filter', nargs='*', help='Word to start filtering the results')
    return parser.parse_args(args)


def startup():
    # check if acestream-engine and acestream-player are available
    if not os.path.isfile(ACESTREAMENGINE) or not os.path.isfile(ACESTREAMPLAYER):
        print "Acestream binaries not found. Please make sure you have AcestreamPlayer and AcestreamEngine installed."
        return False
    return True
    

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
        if not startup():
            exit(1)

        args = parse_arguments(sys.argv[1:])
        exit(main(args.filter))
    except KeyboardInterrupt as e:
        print "Good bye!"

# TODO: check if acestreamengine and acestreamplayer are available (just look for binaries)
# TODO: test what happens if acestreamengine or acestreamplayer are already running.
# TODO: separate channels by language and show in channels menu
