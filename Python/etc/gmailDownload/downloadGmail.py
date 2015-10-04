#!/usr/bin/python
import email, getpass, imaplib
import os
import time
import json
import logging

# TODO: Make some of these command line argument later
IMAP_SERVER = "imap.gmail.com"
SLEEP_INTERVAL_SEC = 5
PAUSE_COUNT = 250

# Required folders
REQUIRED_FOLDER = "[Gmail]/All Mail"

# Configure application log to required level
logging.basicConfig(filename='application.log', level=logging.INFO)

# Dump all the data that looks important, has lot of duplicates, but OK for now. Could 
# get whatever we want later
def dumpMail(mail, mailID):
        data = {}
        data['as_string'] = mail.as_string(True)
        data['is_multipart'] = mail.is_multipart()
        data['preamble'] = mail.preamble
        data['epilogue'] = mail.epilogue
        data['defects'] = mail.defects
        data['keys'] = mail.keys()
        data['items'] = mail.items()

        fp = open(mailID+".mail.inprogress", 'w')                # .inprogress suffix till write is complete - while externally gzipping files, filter .inprogress files
        fp.write(json.dumps(data, indent=4, sort_keys=True))
        fp.close()
	os.rename(mailID+".mail.inprogress", mailID+".mail")
	downloadAttachments(mail, mailID)

# Helper method to just download any attachments in mail
def downloadAttachments(mail, mailID):
        fileNamePrefix = mailID+".mail.attachment-"
        for part in mail.walk():
                if part.get_content_maintype() == 'multipart':
                        continue
                if part.get('Content-Disposition') is None:
                        continue
                filename = part.get_filename()
                counter = 1
                if not filename:
                        filename = 'part-%04d%s' % (counter, 'bin')
                        counter += 1
                fp = open(fileNamePrefix+filename+".inprogress", 'wb')
                fp.write(part.get_payload(decode=True))
                fp.close()
		os.rename(fileNamePrefix+filename+".inprogress", fileNamePrefix+filename)


user = raw_input("Enter your GMail username:")
pwd = getpass.getpass("Enter your password: ")
m = imaplib.IMAP4_SSL(IMAP_SERVER)
m.login(user, pwd)

# Aim is to get all the mails, change folder name if required. m.list() would give all "folders"
m.select(REQUIRED_FOLDER)

resp, items = m.search(None, "ALL")
emailIDs = items[0].split() # getting the mails id
logging.info("Total number of mails: " + str(len(emailIDs)))

# Start fetching from latest to oldest mails
emailIDs.reverse()

pauseCounter = 0
for emailid in emailIDs:
	try:
		resp, data = m.fetch(emailid, "(RFC822)")
		if resp != 'OK':
			logging.error("Failed to fetch mail with id: " + emailid)
			continue
		email_body = data[0][1]
		mail = email.message_from_string(email_body)
		dumpMail(mail, emailid)
		pauseCounter = pauseCounter + 1
		# Would Google throttle/block if I overload ?
		if pauseCounter % PAUSE_COUNT == 0:
			logging.info("Sleeping after so many mails")
			time.sleep(SLEEP_INTERVAL_SEC)
	except Exception, e:
		logging.exception("Had exception when pauseCounter was : " + str(pauseCounter))  # logger.exception grabs and adds exception details by default
		pass  # What can you do, just continue
