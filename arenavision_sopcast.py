#!/home/gerard/.virtualenvs/arenavision/bin/python

import requests
from time import sleep
from datetime import datetime, timedelta
from tabulate import tabulate
from lxml import html
import subprocess
import re
import sys

BASE_URL = "http://arenavision.in/"

SOP_PORT = "8908"


HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'es,ca;q=0.8,en-US;q=0.6,en;q=0.4,:max-age=0',
    'Host': 'arenavision.in',
    'Referer': 'http://arenavision.in/',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.75 Safari/537.36'
}

DATEFORMAT = "%d/%m/%y %H:%M"

CHAN_EXP = "/(AV[0-9]{1,2})"
SPORT_EXP = "CET ([^:]+):"
DESC_EXP = "CET {sport}: (.*)/{join_channels}"

VLC_LOGFILE = "/var/log/output_vlc.log"

class Item(object):
    def __init__(self, data):
        self.time, self.sport, self.match, self.category, self.channels = data        
        self.soplinks = []
    
    def __str__(self):
        return str((self.time, self.sport, self.match, self.category, self.channels, self.soplinks))

    def matches(self, args):
        haystack = str(self).lower()
        return any(arg for arg in args if arg in haystack)


def parse_schedule_row(row):
    # var initialization
    time = sport = match = category = channels = None

    row = row.encode("utf8").strip()
    try:
        time = row[:14]
        time = datetime.strptime(time, DATEFORMAT)
    except Exception, e:
        print e
        return None

    try:                
        sport = re.findall(SPORT_EXP, row)[0]
    except Exception, e:
        print e    
        return None

    try:    
        channels = re.findall(CHAN_EXP, row)
    except Exception, e:
        print e
        return None

    try:
        exp = DESC_EXP.format(sport=sport, join_channels="/".join(channels)) 
        match = re.findall(exp, row)[0]
        category = re.findall("\(([^\(]+)\)", match)[0]
        match = match.replace("({0})".format(category), "").strip()
    except Exception, e:
        print e
        return None

    return time, sport, match, category, channels


def get_page(url):
    req = requests.get(url, headers=HEADERS)
    return req.content


def get_schedule():
    page = get_page(BASE_URL + "agenda")
    tree = html.fromstring(page)
    items = []

    for match in tree.xpath('//div[contains(@class, "field-item")]/p[2]/text()'):
        data = parse_schedule_row(match)
        if data:
        	item = Item(parse_schedule_row(match))
        	items.append(item)

    return items


def crawl_sopcast_links(item):
    for chan in item.channels:
        chan = chan.lower().replace("av", "")
        if int(chan) >= 20:
            page = get_page(BASE_URL + "av" + chan)
            tree = html.fromstring(page)
            link = tree.xpath("//a[contains(@href, 'sop://')]/@href")
            if link:
                item.soplinks.append(link[0])


def show_available_matches(items):
    table = []
    for i, item in enumerate(items, start=1):
        table.append([
            i,
            datetime.strftime(item.time, DATEFORMAT),
            item.sport.decode("utf8"),
            item.category.decode("utf8"),
            item.match.decode("utf8")
        ])
    print tabulate(table)


def clear_screen():
    sys.stdout.write("\033[2J\033[;H")


def print_buffering(value):
    sys.stderr.write("\rBuffering... {0}%".format(value))


def show_match_options(match):
    while True:
        clear_screen()

        print match.match
        print match.time.strftime("%d-%m-%Y %H:%M")
        for i, link in enumerate(match.soplinks, start=1):
            print "  {0} - {1}".format(i, link)

        ch = raw_input("Choose a sopcast channel to start streaming: ")
        
        try:
            soplink = match.soplinks[int(ch) - 1]
        except (IndexError, ValueError) as e:
            print "Type a valid channel: " + str(range(len(match.soplinks)))
            sleep(2)
            continue
        
        start_streaming(match.soplinks[int(ch) - 1])
    
        

def start_streaming(soplink):
    print "Start streaming channel: " + soplink

    vlcoutput = open(VLC_LOGFILE, 'a+')
    vlcrunning = False
    sopprocess = None

    try:
        sopcmd = ["sp-sc-auth", soplink, "3908", SOP_PORT]
        vlccmd = ["vlc", "http://localhost:" + SOP_PORT + "/tv.asf"]

        sopprocess = subprocess.Popen(sopcmd, stdout=subprocess.PIPE)
        print "Wating for stream to buffer"
        print_buffering(0)
        while True:
            line = sopprocess.stdout.readline()
            if "nblockAvailable" in line:
                buff = line.split("nblockAvailable=")[-1]
                print_buffering(buff.strip())
                if int(buff) > 30 and not vlcrunning:
                    subprocess.Popen(vlccmd, stdout=vlcoutput, stderr=vlcoutput)
                    vlcrunning = True
        sopprocess.terminate()
        print "Bye!"
    except KeyboardInterrupt, e:
        print "\nStop stream. Exit."
        sopprocess.terminate()
        raise


def main(args):
    items = get_schedule()

    timelimit = datetime.now() - timedelta(hours=2)
    items = filter(lambda x: x.time > timelimit, items)
    items = sorted(items, key=lambda x: x.sport, reverse=False)

    if args:
        args = (arg.lower() for arg in args)
        items = [item for item in items if item.matches(args)]

    if not items:
        print "No matches found. Exit."
        return 1

    match = None

    while not match:
        # clears the screen 
        clear_screen()
        show_available_matches(items)
        ch = raw_input("Choose a channel or type a sport to filter: ")
        if not ch.isdigit():
            filtered = [item for item in items if item.matches((ch.lower(),))]
            if not filtered:
                print "No results to show, please check your filter"
                sleep(2)
            else:
                items = filtered
        else:
            try:
                match = items[int(ch) - 1] # enumerate starts in 1               
            except IndexError as ie:
                print "Type a valid index channel"
                sleep(2)

    crawl_sopcast_links(match)
    show_match_options(match)
    return 0


if __name__ == "__main__":
    try:
        exit(main(sys.argv[1:]))
    except KeyboardInterrupt as e:
        print "Good bye!"
        exit(0)
    