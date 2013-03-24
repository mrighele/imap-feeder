#!/usr/bin/python
#
# Copyright (c) 2006-2013 Marco Righele <marco@righele.it>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to 
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

try:
    import psyco
    psyco.full()
except:
    pass

import sys
import logging
import feedparser
import os
import os.path
import time

import imap
import cache


def setupLogging(config):
    log_file = config['log']
    logger = logging.getLogger("imap-feeder")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    if log_file == None:
        sth = logging.StreamHandler()
        sth.setLevel(logging.INFO)
        sth.setFormatter(formatter)
        logger.addHandler(sth)
        logger.warn("No log file specified, every thing will go to standard output")
    else:
        sth = logging.StreamHandler()
        sth.setLevel(logging.WARNING)
        sth.setFormatter(formatter)
        logger.addHandler(sth)
        fhnd = logging.FileHandler(log_file)
        fhnd.setLevel(logging.INFO)
        fhnd.setFormatter(formatter)
        logger.addHandler(fhnd)
    return logger


def findConfigFolder():
    import os
    configPath = os.path.join(os.environ['HOME'],'.config')
    if os.environ.has_key('XDG_CONFIG_HOME'):
        configPath = os.environ['XDG_CONFIG_HOME']

    return os.path.join(configPath,"imap-feeder")

configFolder = findConfigFolder()
defaultConfig = os.path.join( configFolder , "config.ini" )

def readConfig(configFile= defaultConfig ):
    import ConfigParser
    result = {}
    cp = ConfigParser.ConfigParser()
    cp.readfp( open(configFile) )
    for item in cp.items("IMAP"):
        result[ item[0] ] = item[1]
    if not 'root-folder' in result:
        result["root-folder"] = ["INBOX"]
    else:
        result["root-folder"] = result["root-folder"].split(".")

    result['log'] = cp.get('general','log')
    return result
    
def login( server, username, password ):
    logger.info("logging in to server %s" % server )
    return imap.IMAP( server, username, password )


def fetchFeeds( feedList ):
    result = []
    for feed in feedList:
        address = feed['url'].strip()
        logger.info("Fetching feed from %s" % address)
        feedInfo =  feedparser.parse( address )
        feedInfo['filters'] = feed.get('filters',[])
        yield feedInfo

def fillMissingInfo(feedInfo):
    """Add some extra information. Also add missing information that we latex expect to always find"""
    feed = feedInfo.feed
    feed['title'] = feed.get('title', feed.get('text', feed.get('info' , feed.get('link', "Unknown"))))
    feed.title = feed['title']

    for entry in feedInfo.entries:
        entry.published_parser = entry['published_parsed'] = entry.get( 'published_parsed' , entry.get( 'updated_parsed', time.localtime() ) )
    
        entry.id = entry['id'] = entry.get( 'id' , entry['title'])
        entry.summary = entry['summary'] = entry.get('summary', entry.get( 'subtitle', entry.get('content', '')))
        entry.summary_detail = entry['summary_detail'] = entry.get('summary_detail', { 'type' : 'text/plain' } )
        entry["links"] = entry.get('links',[])
        entry["enclosures"] = entry.get('enclosures',[])
    
    feedInfo.destinationFolder = feedInfo["destinationFolder"] = feedInfo.feed.title
    return feedInfo


def readFeedsList( filename ):
    import yaml
    data = yaml.load(file(filename).read())

    return data['feeds']


def getFilters(configFolder):
    import sys
    oldPath = sys.path
    sys.path = [configFolder] + sys.path
    try:
        import filter as feedFilter
        sys.path = oldPath
        return feedFilter
    except:
        logger.warning("Unable to load filter file")
        sys.path = oldPath
        class Nothing:
            pass
        return Nothing()



def applyFilters(filters,feedInfo):
    entries = feedInfo['entries']
    for f in filters:
        logger.info("Applying filter %s" % f )
        entries = map(lambda x: f(feedInfo,x),entries)
        entries = filter(lambda x : x != None, entries )
    return entries


def filterFeeds(feedInfo, filters):
    for fi in feedInfo:
        try:
            feed = fi['feed']
            n = len(fi['entries'])
            logger.info("Applying filters to feed %s" % feed['title'])
            feedFilters = []
            for filt in fi['filters']:
                if filt not in dir(filters):
                    logger.error("Invalid filter %s for feed %s" % (filt,feed['title']))
                else:
                    feedFilters.append(getattr(filters,filt))
            logger.info("Using %d filters" % len(feedFilters))
            fi['entries'] = applyFilters(feedFilters,fi)
            logger.info( "Applied %d filters, removed %d entries out of %d" % (len(fi['filters']), n - len(fi['entries']), n))
            yield fi
        except Exception,e:
            logger.error("Error while trying to apply filter to feed %s: %s" % (feed['title'], e))

logger = None
    
def main():
    global logger
    config = readConfig()
    logger = setupLogging(config)
    rootFolder = config["root-folder"]
    server = config["server"]
    username = config["username"]
    password = config["password"]
    ssl = config["ssl"]
    port = None
    if config.has_key("port"):
        port = config["port"]
    if ssl == "False":
        ssl = False
    elif ssl == "True":
        ssl = True
    else:
        logger.critical("Invalid option for ssl: %s" % ssl)
        import sys
        sys.exit(1)
    feedList = readFeedsList( os.path.join( configFolder,"feeds.yaml" ))

    cacheFile = os.path.join(configFolder, "cache.pickle")
    messageCache = cache.MessageCache(cacheFile)
    server = imap.IMAP( server, username, password, ssl, port )
    store = imap.IMAPStore(server, rootFolder, messageCache)
    filters = getFilters(configFolder)

    if not store.checkFolder( [] ):
        logger.error("Unable to create/open root folder %s, aborting" % rootFolder )
        sys.exit(1)
    feedInfos = fetchFeeds( feedList )
    feedInfos = ( fillMissingInfo(fi) for fi in feedInfos )
    feedInfos = filterFeeds(feedInfos, filters)
    for feed in feedInfos:
        store.storeMessages( feed  )
    store.logout()
    messageCache.close()

if __name__ == "__main__":
    main()
