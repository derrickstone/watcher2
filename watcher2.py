# Watcher 2
# 3/24/2017 Derrick Stone
# This script monitors our application servers for timeout and 
# application server errors

import xml.etree.ElementTree
import urllib2, urllib, time, threading, smtplib
from email.mime.text import MIMEText
import MySQLdb

def loadsystemconfig():
	configuration = xml.etree.ElementTree.parse('config.xml').getroot()

	# create some global settings from the system section of the config file
	system={}
	system['pollInterval'] = 120.0
	for s in configuration.find('system').findall('setting'):
		system[s.get('name')]= s.text

	return system

def loadwatchingconfig():
	configuration = xml.etree.ElementTree.parse('config.xml').getroot()
	# load the list of urls to poll
	watching={}
	for u in configuration.find('threads').findall('resource'):
		resource={}
		resource['name']=u.get('name')
		errorState[u.get('name')] = 0
		# add a default timeout and agent
		resource['timeout']=system['defaultTimeout']
		resource['userAgent']=system['defaultUserAgent']
		# STUB: Should be removing whitespace here
		for p in u.findall('property'):
			#print 'adding ', p.get('name')
			resource[p.get('name')]=p.text
		# add a property to monitor the errorlevel
		resource['errorLevel'] = 0
		
		watching[u.get('name')]=resource

	return watching

def loadgroupconfig():
	configuration = xml.etree.ElementTree.parse('config.xml').getroot()
	#load the notification groups		
	groups={}
	for g in configuration.find('recipients').findall('group'):
		r={}
		for x in g.findall('recipient'):
			r[x.get('name')]=x.text
		groups[g.get('name')]=r

	return groups

def recordperformance(system,name,url,duration,errorLevel,errorDetail):
	#if a database is sepecified, write to it, otherwise write to a file
	if system.has_key('dbhost'):
		conn = MySQLdb.connect(user=system['dbusername'],passwd=system['dbpassword'],host=system['dbhost'],db=system['dbname'])
		cursor = conn.cursor()
		cursor.execute("insert into log ( target, url, duration, errorlevel, errordetail ) values ( '%s', '%s', %s, %s, '%s')" % ( name, url, duration, errorLevel, errorDetail ) )
		conn.commit()
		cursor.close()
		conn.close()
	else:
		f = open('log.txt','a')
		f.write("%s\t%s\t%s\t%s\t%s" % name, url, duration, errorLevel, errorDetail)
def checksystems(system,watching,groups):
	#lets try polling our resources
	for i in watching:

		print "testing %s at %s" % (watching[i]['name'] , watching[i]['url'])
		errorLevelThisRun = 0
		errorDetail=""
		duration =0

		agent = system['defaultUserAgent']
		if watching[i]['userAgent'] != '':
			agent = watching[i]['userAgent']

		url = watching[i]['url']

		timeout = system['defaultTimeout']
		if watching[i]['timeout'] != '':
			timeout=watching[i]['timeout']

		headers = { 'User-Agent': agent}	
		values = {}
		data = urllib.urlencode(values)

		req = urllib2.Request(url, data, headers, timeout)
		start = time.clock()
		#first check for service errors
		try: 
			response=urllib2.urlopen(req)
		except URLError as e:
			errorDetail = e.reason
			errorLevelThisRun = 1
		except HTTPError as e:
			errorDetail = e.reason
			errorLevelThisRun = 1

		#then check for application errors
		result=response.read()
		duration = time.clock() - start

		if duration * 1000 >= timeout:
			#taking too long to run, generate an error level
			errorLevelThisRun = 1
			errorDetail = "request exceeded %s timeout" % timeout

		if len(watching[i]['goodText']) > 0 and watching[i]['goodText'] not in result:
			errorDetail = "missing required good text"
			errorLevelThisRun = 1

		if len(watching[i]['badText']) > 0 and watching[i]['badText'] in result:
			errorDetail = "found error text"
			errorLevelThisRun = 1
		
		#print "executed in %s" % duration
		#print "returning an errorLevel of %s" % errorLevelThisRun
		recordperformance(system,watching[i]['name'],url,duration,errorLevelThisRun,errorDetail)

		#either increment the error level or reset it to zero
		if errorLevelThisRun == 1:
			#watching[i]['errorLevel'] = watching[i]['errorLevel']+1
			errorState[watching[i]['name']]=errorState[watching[i]['name']]+1
			print "resource failed"
		else:
			#watching[i]['errorLevel'] = 0
			errorState[watching[i]['name']]=0
			print "resource passed"

		if int(errorState[watching[i]['name']]) == int(watching[i]['errorCountTrigger']):
			print "XXXXXX\nsend a notice\nXXXXX"

			msg=MIMEText('Alert! there is a server problem - %s' % errorDetail)
			msg['Subject']='Server Alert - %s' % watching[i]['name']
			msg['From']='dstone@dstone.com'
			#msg['To']='derrickjstone@gmail.com'
			s=smtplib.SMTP('email-smtp.us-west-2.amazonaws.com')
			s.starttls()
			s.login('dstone@dstone.com','Fr0ntJ@b')

			for recipient in groups[watching[i]['notificationGroup']]:
				#recipient, 
				msg['To']=groups[watching[i]['notificationGroup']][recipient]
				s.sendmail('dstone@dstone.com',msg['To'],msg.as_string())
			s.quit()


		

if __name__ == '__main__':
	#one variable to track ongoing errors
	global errorState 
	errorState= {}

	#load configurations
	system = loadsystemconfig()
	watching = loadwatchingconfig()
	groups = loadgroupconfig()
	

	while True:
		checksystems(system,watching,groups)
		time.sleep(float(system['pollInterval']))
	

print "done!"
