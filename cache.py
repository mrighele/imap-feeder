# Copyright (c) 2012 Marco Righele <marco@righele.it>
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

import pickle
import logging

class MessageCache:
    def __init__(self,filename):
        self.filename = filename
        self.messageLimit = 100
        try:
            self.store = pickle.load(file(filename))
        except:
            self.store = {}

    def close(self):
        pickle.dump(self.store, file(self.filename,"wb"))
            

    def contains(self,feed,id):
        present = feed in self.store and id in self.store[feed]
        logging.info("Checking for presence of %s %s: %s" %(feed,id,present))
        return present

    def add(self,feed,id):
        logging.info("Adding %s %s" %(feed,id))
        if feed not in self.store:
            self.store[feed] = []
        self.store[feed].append(id)
        self.store[feed] = self.store[feed][-self.messageLimit:]
