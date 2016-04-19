#!/bin/env python
# coding:iso-8859-1

# std
import os
import stat
import sys
import re
import getopt
import ConfigParser
import time
import signal
import struct
import select
from SMS import *

from threading import *
from socket import * 

# Mobigen
import Mobigen.Common.Log as Log
import Mobigen.Collector.ColTail as ColTail

# global
SHUTDOWN = False

def Shutdown(num = 0, frame = 0):
	global SHUTDOWN
	SHUTDOWN = True
	__LOG__.Trace("SIGNAL NUM:%s" % num)
	return

signal.signal(signal.SIGINT, Shutdown)
signal.signal(signal.SIGTERM, Shutdown)



class Detect(Thread):


	def __init__(self, target, config, tfile, tprtn, ttime,HOST,PORT,from_num):

		Thread.__init__(self)
		self.smsList = config.options("SMS receive list")
		self.target = target
		self.tfile  = tfile
		self.tprtn  = tprtn
		self.ttime  = ttime
		self.config = config
		self.HOST = HOST
		self.PORT = PORT
		self.from_num = from_num


	def LoadIdx(self):

		fp = open(self.idxFile, "r")
		return fp.read()


	def DumpIdx(self, lineNum):

		fp = open(self.idxFile, "w")
		fp.write(str(lineNum))


	def GetPid(self):

		r = os.popen("ps -ef | grep tail | grep %s | grep -v sh" % self.tfile)
		pid = r.readline().split()[1]
		r.close()
		return int(pid)
		

	def run(self):

		global SHUTDOWN

		# debug
		#self.idxFile = self.tfile + ".info"
		self.idxFile = "./idx.info"
	
		if os.path.isfile(self.idxFile):
			lineNum = self.LoadIdx()
		else:
			lineNum = 0

		self.lineNum = int(lineNum)
		self.rfp = os.popen("tail -n+30730 -f %s" % self.tfile)
		self.pid = self.GetPid()
		__LOG__.Trace("target file = %s" % tfile)

		self.stime = time.time()
		self.csize = os.stat(self.tfile)[stat.ST_SIZE]
		while not SHUTDOWN:

			try:
				input, output, ex = select.select([self.rfp], [], [], 1)
			except Exception, err:
				#if err[0] == "I/O operation on closed file":
				__LOG__.Exception()

			if input:
				try:
					data = self.rfp.readline()
					self.lineNum += 1
					if not data:
						SHUTDOWN = True
						continue
					self.Parser(data)
	
				except:
					__LOG__.Exception()
					SHUTDOWN = True

			self.ReTail()

		
		self.DumpIdx(self.lineNum)


	def ReTail(self):

		if not os.path.isfile(self.tfile):
			__LOG__.Trace("Not found file")
			return

		msize = os.stat(self.tfile)[stat.ST_SIZE]

		# »õ·Î »ý¼º µÆÀ¸¸é
		if int(msize) < int(self.csize):
			os.kill(self.pid, 15)
			self.rfp.close()
			self.rfp = os.popen("tail -n+%s -f %s" %(0,self.tfile))
			self.pid = self.GetPid()
			self.csize = msize
			__LOG__.Trace("reopen target file = %s" % tfile)

		# reload time ÃÊ ¸¶´Ù size¸¦ ±â·ÏÇÑ´Ù.
		if self.TimeCheck():
			self.csize = msize

	
	def TimeCheck(self):

		ctime = time.time()

		# ÇöÀç½Ã°£ÀÌ reload timeÀÌ»ó Áö³µÀ» °æ¿ì
		if (ctime - self.stime) > int(self.ttime):
			self.stime = ctime
			return True

		return False


	def Parser(self, data):

		global SHUTDOWN

		mtime = time.strftime("%H:%M")
		rst = re.search(self.tprtn, data)
		if rst:
			for conf in self.smsList:
				name, num, telecom = self.config.get("SMS receive list", conf).split("|")
				num = "".join(num.split("-"))
				sms = "[%s] %s '%s' error or exception" % (self.target[:20], mtime, data[:16])
				
				if telecom == 'SKT"':
					SendMessage(num, sms,self.HOST,self.PORT,self.from_num)
					__LOG__.Trace("%s %s" % (num, sms))
				else:
					pass		
			#SHUTDOWN = True

if __name__ == '__main__':

	options, args = getopt.getopt(sys.argv[1:], "")
	
	if len(args) != 1:
		print "Usage: %s [CONFIG FILE]" % sys.argv[0]
		print "       %s ./Server_Log_Mon.ini" % sys.argv[0]
		sys.exit()
	cfg = args[0]
	config 	= ConfigParser.ConfigParser()
	config.read(cfg)
	path = config.get("common", "path")
	
	#host/ port/ from_num

	HOST = config.get("SMS_info","HOST")
	HOST = str(HOST)
	print(HOST)
	PORT = config.get("SMS_info","PORT")
	PORT = int(PORT)
	print(PORT)
	from_num = config.get("SMS_info","FROM_NUM")
	print(from_num)
	from_num = str(from_num)





	# Logging
	Log.Init()
	#Log.Init(Log.CRotatingLog(path+"/Server_Log_Mon.log", 10000000, 3))
	__LOG__.Trace("***** Startup Process *****")

	thlst = []
	for target in config.sections():
		if target == "SMS receive list" or target == "common":
			continue
		if target == "Target":
			tfile = config.get(target, "target_file")
			print(tfile)
			tprtn = config.get(target, "target_data_line_pattern")
			ttime = config.get(target, "file_reload_period")

			obj = Detect(target, config, tfile, tprtn, ttime,HOST,PORT,from_num)
			obj.setDaemon(True)
			obj.start()
    		thlst.append(obj)

	for th in thlst:
		th.join()

	__LOG__.Trace("***** END Process *****")

