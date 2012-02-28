Introduction
============

This is a program to save feed entries as Imap messages on a mail server.

Single messages can be filtered or transformed by python scripts.

It's tested only my machine (running Dovecot as Imap server), so YMMV (feedback welcome).


Requirements
============

- A decently recent version of python 2.x (2.6 is fine, but older versions should work too)
- feedparser
- python-yaml

Setup
=====

Create the folder $HOME/.config/imap-feeder
Create the following files inside that folder:

* config.ini for the configuration of the connection
* feeds.yaml for the list of feeds
* filter.py for the filters/transformation function.

For each of these file there is a sample together with
the source code

Running
=======

Run main.py, possibly as a cron job


