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

# Checkpoint progress as my Raspberry pi seems to die unexpectedly, a lot
CHECKPOINT = ".checkpoint"

# Configure application log to required level
logging.basicConfig(filename='application.log', level=logging.INFO)


# get_payload() would return a list of Message-objects if its multipart else a string, this helper 
# method wraps that by recursively extracting and returning entire payload
def extractPayload(mail):
        if mail.is_multipart():
                # Recursively extract payload if it is multipart
                data = ''
                for part in mail.get_payload():
                        data = data + extractPayload(part)
                return data
        else:
                # If its not multipart, payload would be string and just return it
                return mail.get_payload()

# Dump all the data that looks important, has lot of duplicates, but OK for now. Could 
# get whatever we want later
def dumpMail(mail, mailID):
        data = {}
        data['is_multipart'] = mail.is_multipart()
        data['preamble'] = mail.preamble
        data['epilogue'] = mail.epilogue
        data['defects'] = mail.defects
        data['keys'] = mail.keys()
        data['items'] = mail.items()
        data['payload'] = extractPayload(mail)

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


# Based on where the checkpoint is, return mailIDs that aren't (probably) processed yet. 
# Could use the filenames of stored mails, but this is cleaner approach
def loadState(mailIDList):
        if os.path.isfile(CHECKPOINT) == False:
                return mailIDList
        try:
                # Checkpoint file exists - load it
                fp = open(CHECKPOINT)
                checkpoint = fp.readline().strip()
                if checkpoint in mailIDList:
                        logging.info("Loading checkpoint: " + checkpoint + "  at mailID-list index: " + str(mailIDList.index(checkpoint)))
                        return mailIDList[mailIDList.index(checkpoint)+1:]
        except Exception,e:
                logging.exception("Checkpoint method failed strangely!")
                pass
        logging.info("Couldn't load any state")
        return mailIDList

# Save checkpoint
def saveState(mailID):
        nextCheckpoint = CHECKPOINT+'.next'
        fp = open(nextCheckpoint, 'w')  
        fp.write(mailID)
        fp.close()
        os.rename(nextCheckpoint, CHECKPOINT)   # Once next checkpoint is committed completely, make it actual checkpoint


# Main

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

# Start where we were interrupted
emailIDs = loadState(emailIDs)

logging.info("Starting at mailID: " + emailIDs[0])

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
                # Commit progress till now
                saveState(emailid)
		pauseCounter = pauseCounter + 1
		# Would Google throttle/block if I overload ?
		if pauseCounter % PAUSE_COUNT == 0:
			logging.info("Sleeping after so many mails")
			time.sleep(SLEEP_INTERVAL_SEC)
	except Exception, e:
		logging.exception("Had exception when pauseCounter was : " + str(pauseCounter))  # logger.exception grabs and adds exception details by default
		pass  # What can you do, just continue
