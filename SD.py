import irc
import irc.bot
from irc.bot import SingleServerIRCBot
from wikitools import *
import thread
import threading
import sys
import time
from datetime import datetime
import os

site = wiki.Wiki()
site.login('DatBot','redacted')
useAPI = True
ctitle = 'Category:Candidates for speedy deletion'
connections = {}

class timedTracker(dict):
    def __init__(self, args={}, expiry=300):
        dict.__init__(self, args)
        self.expiry = expiry
        self.times = set()
        self.times = set([(item, int(time.time())) for item in self.keys()])
        
    def __purgeExpired(self):
        checktime = int(time.time())-self.expiry
        removed = set([item for item in self.times if item[1] < checktime])
        self.times.difference_update(removed)
        [dict.__delitem__(self, item[0]) for item in removed]
        
    def __getitem__(self, key):
        self.__purgeExpired()
        if not key in self:
            return 0
        return dict.__getitem__(self, key)
    
    def __setitem__(self, key, value):
        self.__purgeExpired()
        if not key in self:
            self.times.add((key, int(time.time())))
        return dict.__setitem__(self, key, value)
    
    def __delitem__(self, key):
        self.times = set([item for item in self.times if item[0] != key])
        self.__purgeExpired()
        return dict.__delitem__(self, key)
    
    def __contains__(self, key):
        self.__purgeExpired()
        return dict.__contains__(self, key)
    
    def __repr__(self):
        self.__purgeExpired()
        return dict.__repr__(self)
        
    def __str__(self):
        self.__purgeExpired()
        return dict.__str__(self)
    
    def keys(self):
        self.__purgeExpired()
        return dict.keys(self)
        
def normTS(ts): # normalize a timestamp to the API format
    ts = str(ts)
    if 'Z' in ts:
        return ts
    ts = datetime.datetime.strptime(ts, "%Y%m%d%H%M%S")
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")

def logFromAPI(lasttime):
    lasttime = normTS(lasttime)
    params = {'action':'query',
        'utf8':'1',
        'formatversion':'2',
        'prop':'revisions',
        'generator':'categorymembers',
        'gcmtitle':ctitle,
        'gcmprop':'timestamp|title',
        'gcmdir':'older',
        'gcmsort':'timestamp',
        'gcmlimit':'0',
    }
    req = api.APIRequest(site, params)
    res = req.query(False)
    rows = res['query']['pages']
    #if len(rows) > 0:
        #del rows[0] # The API uses >=, so the first row will be the same as the last row of the last set
    ret = []
    for row in rows:
        entry = {}
        entry['ns'] = row['ns']
        p = page.Page(site, row['title'], check = False)
        entry['t'] = p.unprefixedtitle
        for row in row['revisions']:
            entry['u'] = row['user']
            entry['c'] = row['comment']
            entry['ts'] = row['timestamp']
        ret.append(entry)
    return ret

class CommandBot(SingleServerIRCBot):
    def __init__(self, channel, nickname, server, port=6667):
        SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.channel = channel
    def on_nicknameinuse(self, c, e):
        print "Nickname in use"
        thread.interrupt_main()
    def on_welcome(self, c, e):
        global connections
        c.privmsg("NickServ", "identify redacted")
        time.sleep(3)
        c.join(self.channel)
        connections['command'] = c
        sendToChannel("Bot initialised")
        return
	    
def sendToChannel(msg):
    connections['command'].privmsg("#wikipedia-en-csd", msg)
	
class BotRunnerThread(threading.Thread):
    def __init__(self, bot):
        threading.Thread.__init__(self)
        self.bot = bot
    def run(self):
        self.bot.start()
		
def getStart():
    if useAPI:
	    params = {'action':'query',
		    'list':'categorymembers',
                    'utf8':'1',
                    'cmtitle':ctitle,
		    'cmprop':'ids|timestamp',
		    'cmlimit':'1',
	    }
	    req = api.APIRequest(site, params)
	    res = req.query(False)
	    row = res['query']['categorymembers'][0]
	    lasttime = row['timestamp']
    return (lasttime)
def main():
    global connections
    Cchannel = "#wikipedia-en-csd"
    channel = "#wikipedia-en-csd"
    Cserver = "irc.freenode.net"
    nickname = "DatBotCSD"
    cbot = CommandBot(Cchannel, nickname, Cserver)
    cThread = BotRunnerThread(cbot)
    cThread.daemon = True
    cThread.start()
    IRCreported = timedTracker(expiry=60)
    titles = timedTracker()
    while len(connections) != 1:
        time.sleep(2)
        print("In while")
    time.sleep(5)
    while True:
        (lasttime) = getStart()
        if useAPI:
            rows = logFromAPI(lasttime)
        for row in rows:
            ns = row['ns']
            title = row['t']
            user = row['u']
            es = row['c']
            timestamp = row['ts']
            titles[(ns,title)]+=1
            if titles[(ns,title)]==1 and not (ns, title) in IRCreported:
                p = page.Page(site, title, check = False)
                print '%s added a CSD tag to %s with the edit summary "%s" - https://en.wikipedia.org/wiki/%s' %(user, p.title, es, p.urltitle)
                del titles[(ns,title)]
                IRCreported[(ns,title)] = 1
                
if __name__ == "__main__":
	main()
