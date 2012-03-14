#
# Copyright (c) 2006-2012 Marco Righele <marco@righele.it>
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

"""
A simple class that abstracts the details of the IMAP server connection.
"""

__all__ = [ "IMAP", "IMAPStore" ] 

import imaplib
import logging 
import re
import time

from email.MIMEText import MIMEText
import time

defaultFrom = "FeedMailer@localhost"



def toBool( result ):
    if result == "OK":
        return True
    else:
        return False

def sanitize( imapName ):
    imapName = re.sub("\.","_",imapName)
    imapName = re.sub('"',"'",imapName)
    return re.sub("&","&-",imapName)

def quote( path ):
    assert(type(path)==list)
    
    cleanPath = [ sanitize(item) for item in path ]
    
    return '"' + '.'.join(cleanPath)  + '"'



def htmlLinks( entry ):
    """
    Create an html snippet for the link section of the message
    """
    if entry.links == []:
        return ""
    result = "\n<hr>\n<b>Links:</b><br />"
    for l in entry.links:
        result += '<a href="' + l.href + '">' + l.href + "</a>"
        result += "<br />\n"
    return result

def htmlEnclosures( entry ):
    """
    Create an html snippet for the enclosures section of the message
    """
    if entry.enclosures == []:
        return ""
    result = "\n<hr>\n<b>Enclosures:</b><br />"
    for l in entry.enclosures:
        result += '<a href="' + l.href + '">' + l.href + "</a>"
        result += "<br />\n"
    return result
    

def createMessageBody( feedInfo, entry, dest ):
    body = entry.summary
#    type = "plain"
#    if entry.summary_detail["type"] == "text/html":
    links = htmlLinks( entry )
    enclosures = htmlEnclosures( entry )
    body = body + links + enclosures

    charset = None    
    if type(body) == unicode:
        body = body.encode("utf-8")
        charset = "utf-8"
    
    subtype = "html"
    msg = MIMEText( body, subtype, charset )
    msg["Subject"] = entry.title
    msg["From"] = feedInfo.feed.title + " <" + defaultFrom + ">"
    msg["To"] = dest
    msg["Date"] = time.asctime( entry.published_parsed )
    if "id" in entry:
        msg["X-Entry-ID"] = entry.id
    return msg


    
class IMAP:
    def __init__(self,address,username,password, ssl=False,port = None):
        if ssl:
            Server = imaplib.IMAP4_SSL
        else:
            Server = imaplib.IMAP4
        if port == None and not ssl:
            port = 143
        if port == None and ssl:
            port = 993

        self.server = Server(address,port)
        self.server.login( username, password )
        self.username = username
        self.address = address
   
       
    def select(self,mailbox=["INBOX"]):
        assert(type(mailbox) == list )
        q = quote(mailbox)
        result, msg = self.server.select(q)
        if not toBool(result):
            logging.warning("Folder %s selection failed: " % q  + msg[0] )
        return toBool(result)
        
    def search(self, charset=None,headers=None,since=None):
        criteria = []
        if headers != None:
            for k,v in headers.iteritems():
                criteria += ["HEADER",k,v]
        if since != None:
            criteria += ["SINCE", imaplib.Time2Internaldate(since)[:-16] + '"']
        if criteria == []:
            criteria = "ALL"
        result, messages = self.server.search( charset, *criteria )
        if toBool(result) == True:
            return [ int(msgNumber) for msgNumber in messages[0].split() ]
        logging.warning("Search returned the following error: " + messages[0] )
        return []
        

    def logout(self):
        self.server.logout()

    def create(self,mailbox):
        assert(type(mailbox) == list )
        m = quote(mailbox)
        logging.info("Creating mailbox %s" % m)
        result,msg = self.server.create( m )
        if not toBool(result):
            logging.warning("Folder creation failed: " + msg[0] )
        return toBool(result)

    def delete(self,mailbox):
        assert(type(mailbox) == list )
        m = quote(mailbox)
        logging.info("Removing mailbox %s" % m)
        result,msg = self.server.delete(mailbox)
        if not toBool(result):
            logging.info("Folder remove failed: " + msg[0] )
        return toBool(result)
                
    def append(self, folder, charset, datetime, message ):
        ok, msg = self.server.append(quote(folder),charset,datetime,message)
        return toBool(ok)
        
    def close(self):
        self.server.close()
                       
class IMAPStore:
    """
    A class to handle the operation on the feeds on the IMAP server
    """
    def __init__(self, server, root, cache):
        self.server = server
        self.root = root
        self.cache = cache
        assert( type(root) == list )
        
    def getMessageById( self, feedInfo , id ):
        fullPath =  self.root + [feedInfo["destinationFolder"]]
        if not self.server.select( fullPath ):
            return None
            
        messages = self.server.search(None, headers = { "X-Entry-ID" : str(id) } )
        if len( messages ) == 0:
            return None
        if len( messages ) > 1:
            logging.warning("Found more than one entry with id %s in folder %s" % (id, feedInfo["destinationFolder"] ) )
        return messages[0]
        
    def checkFolder( self, folder):
        logging.debug("Selecting folder %s" % folder )
        fullPath = self.root + folder
        if self.server.select( fullPath ):
            return True
        logging.warning( "Unable to select folder %s, I'll try to create it" % fullPath )
        if self.server.create( fullPath ):
            return True
        logging.warning("Unable to create folder %s" % fullPath )
        return False

    def isLatest(self, entry ):
        """
        Return True if there are entries newer that the one given as argument
        Suppose that we are already on the right folder
        """        
        result = self.server.search( since = entry.published_parsed )
        return result != []


    def alreadySeen(self, feedInfo, entry):
        return ( self.cache.contains(feedInfo['href'],entry.id) or
                 # fallback in case we lost the cache
                 self.getMessageById( feedInfo, entry.id ) != None or
                 self.isLatest(entry))


    def storeMessages( self, feedInfo ):
        logging.debug("Sending messages for feed %s" % feedInfo.feed.title)    
        # Da sistemare
        dest = self.server.username + "@" + self.server.address
        
        
        destFolder = [feedInfo.destinationFolder]
        fullPath = self.root + destFolder
        ok = self.checkFolder( destFolder )
        if not ok:
            logging.warning("Unable to create folder, skipping this feed")
            return False
        if not self.server.select( self.root + destFolder ):
            logging.warning("Unable to select folder, will skip this feed")
            return False

        def entryCmp(x,y):
            xtime = time.mktime(x.published_parsed)
            ytime = time.mktime(y.published_parsed)
            return int(xtime - ytime)

        feedInfo.entries.sort( entryCmp )
        todo=[]
        for entry in feedInfo.entries:
            try:
                if self.alreadySeen(feedInfo,entry):
                    logging.debug("Message with id %s already sent" % entry.id )
                    continue
                todo.append(entry)
            except Exception, e:
                logging.warning("Unhandled exception while storing messages:: %s" % str(e) )
        logging.info( "Sending %d messages for feed %s" % (len(todo), feedInfo.feed.title))
        for entry in todo:
            try:
                msg = createMessageBody( feedInfo, entry, dest )
                datetime = entry.published_parsed
                logging.debug("Sending message %s" % entry.title )
                msgText = msg.as_string()
                if self.server.append( fullPath , None, datetime, msgText ):
                    self.cache.add(feedInfo['href'], entry.id )
                else:
                    logging.warning("Unable to store message %s" % entry.title)

            except Exception, e:
                logging.warning("Unhandled exception: %s" % str(e) )
        self.server.close()
        
    def logout(self):
        self.server.logout()
 
