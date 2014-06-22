from Phidgets.PhidgetException import PhidgetErrorCodes, PhidgetException
from Phidgets.Events.Events import AttachEventArgs, DetachEventArgs, ErrorEventArgs, InputChangeEventArgs, OutputChangeEventArgs, SensorChangeEventArgs
from Phidgets.Devices.InterfaceKit import InterfaceKit
from time import localtime, strftime


#Basic imports
from ctypes import *
import sys
import os
import random
import time
import operator
import threading
import audiere

# Global variables/flags

# Test and devel environment
testEnv = True

global maxLogSize
if (testEnv == True):
	maxLogSize = 20000 # bytes
else:
	maxLogSize = 2000000 # bytes

# Times and intervals
nightModeBeginHour = 23 # HH
nightModeEndHour = 8 # H
nightModeMultiplication = 5 # Would be multiplied to the maximumInterval to make longer sleeping intervals for the nights 

# Paths absolute or relative with / at the end
reportArchivePath = './log/archive/'
reportPath = './log/'
soundPath = './sound/zara/'
interfaceSoundPath = './sound/interface/'
testSoundPath = './sound/test/'

# Names of the files.
pickupReportFilename = "pickup.txt"
finishedFileReportFilename = "finish.txt"

# Ring config 
if (testEnv == True):
	maximumSleepInterval = 10
	ringingTimes = 6
	ringingLength = 3 # Seconds
	ringingPauseLength = 2 # Seconds
else:
	maximumSleepInterval = 300 # Seconds. 5 mins.
	ringingTimes = 6
	ringingLength = 3 # Seconds
	ringingPauseLength = 2 # Seconds

# Flags
global phidgetClosing
global sleeping
global loadFileDuringSleep
global playingSound
global playingSoundOutro
global playingSoundDial
global playingSoundBusy
global receiverPicked
global markreceiverPicked
global markCompleteListened

phidgetClosing = False
loadFileDuringSleep = False
sleeping = False
playingSound = False
playingSoundOutro = False
playingSoundDial = False
playingSoundBusy = False
receiverPicked = False
markreceiverPicked = False
markCompleteListened = False

# Opening audio device
d = audiere.open_device()	

def sendEmailReport(subject, bodyText):
	try:
		sendmail_location = "/usr/sbin/sendmail" # sendmail location
		p = os.popen("%s -t" % sendmail_location, "w")
		p.write("From: %s\n" % "from@example.com")
		p.write("To: %s\n" % "to@example.com")
		p.write("Subject: DerBeweis - Report - " + subject + "\n")
		p.write("\n") # blank line separating headers from body
		p.write(bodyText)
		status = p.close()
		print "Reporting: Sendmail exit status", status
	except:
		print "reporting: Sending email encountered an exception."
		pass

## Phidget event handling functions
#Information Display Function
def displayDeviceInfo():
    print("|------------|----------------------------------|--------------|------------|")
    print("|- Attached -|-              Type              -|- Serial No. -|-  Version -|")
    print("|------------|----------------------------------|--------------|------------|")
    print("|- %8s -|- %30s -|- %10d -|- %8d -|" % (interfaceKit.isAttached(), interfaceKit.getDeviceName(), interfaceKit.getSerialNum(), interfaceKit.getDeviceVersion()))
    print("|------------|----------------------------------|--------------|------------|")
    print("Number of Digital Inputs: %i" % (interfaceKit.getInputCount()))
    print("Number of Digital Outputs: %i" % (interfaceKit.getOutputCount()))
    print("Number of Sensor Inputs: %i" % (interfaceKit.getSensorCount()))

#Event Handler Callback Functions
def interfaceKitError(e):
    source = e.device
    print("InterfaceKit %i: Phidget Error %i: %s" % (source.getSerialNum(), e.eCode, e.description))

def interfaceKitInputChanged(e):
	global markreceiverPicked
	global receiverPicked
	
	source = e.device
	print("InterfaceKit %i: Input %i: %s" % (source.getSerialNum(), e.index, e.state))
	
	if (e.state == True):
		#time.sleep(3)
		if (interfaceKit.getInputState(0) == True and interfaceKit.getInputState(0) == e.state):
			receiverPicked = True
			markreceiverPicked = True	
	else:
		receiverPicked = False

def interfaceKitOutputChanged(e):	
	source = e.device
	print("InterfaceKit %i: Output %i: %s" % (source.getSerialNum(), e.index, e.state))

def inferfaceKitAttached(e):
   attached = e.device
   print("InterfaceKit %i Attached!" % (attached.getSerialNum()))

def interfaceKitDetached(e):
	detached = e.device
	print("InterfaceKit %i Detached!" % (detached.getSerialNum()))
	sendEmailReport('Phidget Detached', "InterfaceKit %i Detached!" % (detached.getSerialNum()))


# Main threads
class pthread(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
	
	def run(self):
		global phidgetClosing
		global sleeping
		try:
			interfaceKit.openPhidget()
		except PhidgetException as e:
			print("Phidget Exception %i: %s" % (e.code, e.details))
			print("Exiting....")
			exit(1)
		
		print("Phidget: Waiting for attach....")
		
		try:
			interfaceKit.waitForAttach(1000)
		except PhidgetException as e:
			print("Phidget Exception %i: %s" % (e.code, e.details))
			try:
				interfaceKit.closePhidget()
			except PhidgetException as e:
				print("Phidget Exception %i: %s" % (e.code, e.details))
				print("Exiting....")
				exit(1)
		# If there was no excpetion while attaching
		else:
			pass
			displayDeviceInfo()
		
		if (testEnv == False):
			print("Setting the data rate for each sensor index to 4ms....")
		
			for i in range(interfaceKit.getSensorCount()):
				try:
					interfaceKit.setDataRate(i, 4)
				except PhidgetException as e:
					print("Phidget Exception %i: %s" % (e.code, e.details))
		
		print("Phidget: Press Enter to quit....")
		chr = sys.stdin.read(1)
		
		# Enter pressed. We close the phidget.
		phidgetClosing = True
		
		# If sleeping, explain the reason for the delayed exit.
		if (sleeping == True):
			print("Phidget: Closing after sleep time is over...")
			sleeping = False
		else:
			# Or jump out right away.
			print("Phidget: Closing...")
		
		# Closing the phidget object	
		try:
			interfaceKit.closePhidget()
		except PhidgetException as e:
			print("Phidget Exception %i: %s" % (e.code, e.details))
			print("Exiting....")
			exit(1)
		
		print("Phidget: Done.")
		exit(0)	
	

class mediaLoader(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
	
	def run(self):
		global playingSound
		global sleeping
		global playingSoundOutro
		global playingSoundDial
		global playingSoundBusy
		global receiverPicked
		global loadFileDuringSleep
		global phidgetClosing
		global markCompleteListened
		
		try:
			# Initial load of the files
			soundFile = d.open_file(soundPath + '01.mp3')
			soundFileOutro = d.open_file(interfaceSoundPath + 'outro.mp3')
			soundFileBusy = d.open_file(interfaceSoundPath + 'busy.mp3')
			soundFileDial = d.open_file(interfaceSoundPath + 'dial.mp3')
		except Exception as e:
			print("mediaLoader: File Exception!")
			sendEmailReport("File Exception", "mediaLoader: File Exception!")
		while (phidgetClosing == False):
			# The receiver is on the phone
			if (receiverPicked == False):
				# Stop any playing sound files
				if (soundFile.playing == True):
					soundFile.stop()
					playingSound = False
				else:
					playingSound = False
					
				if (soundFileOutro.playing == True):
					soundFileOutro.stop()
					playingSoundOutro = False
					
				if (soundFileBusy.playing == True):
					soundFileBusy.stop()
					playingSoundBusy = False
					
				if (soundFileDial.playing == True):
					soundFileDial.stop()
					playingSoundDial = False
					
				if (testEnv == True):
					numberOfFilesToLoad = 5
				elif (testEnv == False):
					numberOfFilesToLoad = 57
				# IF loading while sleeping is active.
				if (loadFileDuringSleep == True):
					fileNumber = int(round(random.random() * numberOfFilesToLoad))
					# If the generated number is less than 10, add a 0 in front to match the real filenames.
					if (fileNumber < 10):
						fileNumberString = '0' + str(fileNumber)
					else:
						fileNumberString = str(fileNumber)
						
					print ("mediaLoader: File " + fileNumberString + '.mp3' + " is being loaded...")
					
					try:
						if (testEnv == True):
							soundFile = d.open_file(testSoundPath + 'K' + fileNumberString + '.mp3')
						elif (testEnv == False):
							soundFile = d.open_file(soundPath + fileNumberString + '.mp3')
					except Exception as e:
						print("mediaLoader: File Exception!")
						sendEmailReport("File Exception", "mediaLoader: File Exception!")
					
					# Set the flag to false when the file was loaded.
					loadFileDuringSleep = False
			# The receiver is picked and the phone is not sleeping or the phidget closing.
			elif (receiverPicked == True and sleeping == False):
				if (phidgetClosing == False):
					# Set the relay output to False.
					#if (phidgetClosing == False and playingSound == False):
					interfaceKit.setOutputState(0, False)
			
					if (playingSound == False and playingSoundDial == False and fileNumberString <> None):
						print ("mediaLoader: Playing sound file " + fileNumberString + '.mp3')
						soundFile.play()
						playingSound = True
						playingSoundOutro = False
					elif (playingSound == True and soundFile.playing == False and playingSoundOutro == False):
						if (soundFileOutro.playing == False and playingSoundOutro == False):
							print ("mediaLoader: Playing outro...")
							playingSoundOutro = True
							playingSoundBusy = False
							soundFileOutro.play()
					elif (playingSound == True and soundFile.playing == False and playingSoundOutro == True and soundFileOutro.playing == False):
						if (soundFileBusy.playing == False and playingSoundBusy == False):
							print ("mediaLoader: Playing busy signal...")
							soundFileBusy.play()
							soundFileBusy.repeating = 1
							playingSoundBusy = True
							markCompleteListened = True
			
			# If the phone is sleeping and receiver picked, play the dial signal (free line).
			elif (receiverPicked == True and sleeping == True):
				sleeping = True
				if (soundFileDial.playing == False):
					print ("mediaLoader: Playing dial signal...")
					soundFileDial.play()
					soundFileDial.repeating = 1
					playingSoundDial = True
	

class reporting(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
	
	def run(self):
		global playingSound
		global playingSoundOutro
		global phidgetClosing
		global markreceiverPicked
		global markCompleteListened
		global maxLogSize
				
		while (phidgetClosing == False):
			
			if (os.path.exists(reportPath + pickupReportFilename) and os.path.exists(reportPath + finishedFileReportFilename)):
				if (os.path.getsize(reportPath + pickupReportFilename) > maxLogSize):
					print "reporting: Archiving " + reportPath + pickupReportFilename + " to pickup-" + str(time.time()) + ".txt ..."
					os.system('mv ' + reportPath + pickupReportFilename + ' ' + reportArchivePath + 'pickup-' + str(time.time()) + ".txt")
					os.system('echo > ' + reportPath + pickupReportFilename)
			
				if (os.path.getsize(reportPath + finishedFileReportFilename) > maxLogSize):
					print "reporting: Archiving " + reportPath + finishedFileReportFilename + " to " + 'finish-' + str(time.time()) + ".txt ..."
					os.system('mv ' + reportPath + finishedFileReportFilename + ' ' + reportArchivePath + 'finish-' + str(time.time()) + ".txt")
					os.system('echo > ' + reportPath + finishedFileReportFilename)
			else:
				os.system('echo > ' + reportPath + finishedFileReportFilename)
				os.system('echo > ' + reportPath + pickupReportFilename)
			
			if (markreceiverPicked == True and playingSound == True):
				print "reporting: Writing visitor receiver pickup report to file..."
				file = open(reportPath + pickupReportFilename, 'a', 0)
				dateTimePicked = strftime("%H:%M - %A %d. %B %Y", localtime())
				file.write(dateTimePicked + "\n")
				markreceiverPicked = False
				file.close()
			
			if (markCompleteListened == True and playingSound == True):
				print "reporting: Writing complete listened story report to file..."
				file = open(reportPath + finishedFileReportFilename, 'a', 0)
				dateTimePicked = strftime("%H:%M - %A %d. %B %Y", localtime())
				file.write(dateTimePicked + "\n")
				markCompleteListened = False
				file.close()
	

class background(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)	
	
	def ringLogic(self, maximumInterval, ringTimes, ringLength, ringPauseLength):
		global phidgetClosing
		global loadFileDuringSleep
		global sleeping
		
		currentTimeOfDay = int(strftime("%H", localtime()))
			
		# Configuring the ringing intervals for night mode
		if ( currentTimeOfDay > nightModeBeginHour and currentTimeOfDay < nightModeEndHour and currentTimeOfDay > 24 - nightModeBeginHour):
			ringingInterval = round(random.random() * maximumInterval * nightModeMultiplication)
			print "background: Set to the night mode. Ringing every " + str(ringingInterval) + " seconds."
		else:
			ringingInterval = round(random.random() * maximumInterval)
			print "background: Set to the day mode. Ringing every " + str(ringingInterval) + " seconds."
		
		loadFileDuringSleep = True
		print ("background: Sleeping for " + str(ringingInterval) + " seconds.")
		sleeping = True
		time.sleep(ringingInterval)
		sleeping = False
		loadFileDuringSleep = False
		
		if (phidgetClosing == False):
			try:
				if (interfaceKit.getOutputState(0) == False):
					for i in range(ringTimes):
						if (receiverPicked == True or phidgetClosing == True):
							break
					
						# Ring ...
						interfaceKit.setOutputState(0, True)
					
						# Keep ringing for 3 seconds
						for i in range(ringLength):
							if (receiverPicked == True  or phidgetClosing == True):
								break
							time.sleep(1)
					
						if (receiverPicked == True or phidgetClosing == True):
							break
				
						# Stop ringing, pause between rings
						interfaceKit.setOutputState(0, False)
			
						# Pause ringing for two seconds
						for i in range(ringPauseLength):
							if (receiverPicked == True  or phidgetClosing == True):
								break
							time.sleep(1)
							
						if (receiverPicked == True  or phidgetClosing == True):
							break
				else:
					interfaceKit.setOutputState(0, False);
			except PhidgetException as e:
				print("Phidget Exception %i: %s" % (e.code, e.details))
				sendEmailReport("Exited", "Phidget Exception %i: %s" % (e.code, e.details))
				#raise
				exit(1)
	
	def run(self):
		global playingSound
		global receiverPicked
		global loadFileDuringSleep
		while (phidgetClosing == False):
			if (receiverPicked == False):
				# Every 100 seconds, ring 6 times, each time 3 seconds with 2 seconds pauses.
				self.ringLogic(maximumSleepInterval, ringingTimes, ringingLength, ringingPauseLength)
			else:
				if (phidgetClosing == False):
					interfaceKit.setOutputState(0, False)
	
# Main program code
#Create an interfacekit object
try:
    interfaceKit = InterfaceKit()
except RuntimeError as e:
	print("Phidget: Runtime Exception: %s" % (e.details))
	print("Phidget: Exiting....")
	exit(1)
		
# Assigning phidgets event-handling functions to phidget object events
try:
	interfaceKit.setOnAttachHandler(inferfaceKitAttached)
	interfaceKit.setOnDetachHandler(interfaceKitDetached)
	if (testEnv == False):
		interfaceKit.setOnErrorhandler(interfaceKitError)
	interfaceKit.setOnInputChangeHandler(interfaceKitInputChanged)
	interfaceKit.setOnOutputChangeHandler(interfaceKitOutputChanged)
except PhidgetException as e:
	print("Phidget Exception %i: %s" % (e.code, e.details))
	print("Phidget: Exiting....")
	exit(1)
	
# Opening the phidget object
print("Phidget: Opening phidget object....")
try:
	interfaceKit.openPhidget()
except PhidgetException as e:
	print("Phidget: Phidget Exception %i: %s" % (e.code, e.details))
	print("Phidget: Exiting....")
	exit(1)
	
# Initiating threads
media = mediaLoader()
phid = pthread()
back = background()
report = reporting()
	
phid.start()
media.start()
back.start()
report.start()

phid.join()
media.join()
back.join()
report.join()
