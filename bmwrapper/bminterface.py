import ConfigParser
import base64
import xmlrpclib
import json
import datetime
import time
import email.utils
import os
import logging

purgeList = []
allMessages = []
currentAddress = None

def _getKeyLocation():  #make this not suck later
    return '~/.config/PyBitmessage/keys.dat'

def _getConfig(keys):
    return apiData()
    #TODO make this work, so the above can be removed
    config = ConfigParser.SafeConfigParser()
    config.read(keys)
    try:
      api_port = config.getint('bitmessagesettings', 'apiport')
      api_iface = config.get('bitmessagesettings', 'apiinterface')
      api_uname = config.get('bitmessagesettings', 'apiusername')
      api_passwd = config.get('bitmessagesettings', 'apipassword')
    except:
        logging.warning("Could not load keys.dat config")
        return 0
    return "http://"+api_uname+":"+api_passwd+"@"+api_iface+":"+str(api_port)+"/"

def _makeApi(keys):
    return xmlrpclib.ServerProxy(_getConfig(keys))
    
def _sendMessage(toAddress, fromAddress, subject, body):
    api = _makeApi(_getKeyLocation())
    try:
      return api.sendMessage(toAddress, fromAddress, subject, body)
    except:
      return 0
      
def _sendBroadcast(fromAddress, subject, body):
    api = _makeApi(_getKeyLocation())
    try:
      return api.sendBroadcast(fromAddress, subject, body)
    except:
      return 0
      
def _stripAddress(address):
    if 'broadcast' in address.lower():
      return 'broadcast'

    orig = address
    alphabet = '123456789abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ'
    retstring = ''
    while address:
      if address[:3] == 'BM-':
        retstring = 'BM-'
        address = address[3:]
        while address[0] in alphabet:
          retstring += address[0]
          address = address[1:]
      else:
        address = address[1:]
    logging.info("Converted address " + orig + " to " + retstring)
    return retstring

def registerAddress(address):
    global currentAddress
    currentAddress = address
    logging.debug("Set current address to %s" % currentAddress)

def send(toAddress, fromAddress, subject, body):
    toAddress = _stripAddress(toAddress)
    fromAddress = _stripAddress(fromAddress)
    subject = subject.encode('base64')
    body = body.encode('base64')
    if toAddress == 'broadcast':
      return _sendBroadcast(fromAddress, subject, body)
    else:
      return _sendMessage(toAddress, fromAddress, subject, body)

def _getAll():
    global allMessages
    global currentAddress
    if not allMessages:
      api = _makeApi(_getKeyLocation())
      allMessages = json.loads(api.getAllInboxMessages())
    logging.debug("Current filtering address is %s" % currentAddress)
    if currentAddress is not None:
        ret = []
        for msg in allMessages['inboxMessages']:
            if msg['toAddress'] == currentAddress:
                ret.append(msg)
        return dict(inboxMessages=ret)
    return allMessages

def get(msgID):
    inboxMessages = _getAll()
    dateTime = email.utils.formatdate(time.mktime(datetime.datetime.fromtimestamp(float(inboxMessages['inboxMessages'][msgID]['receivedTime'])).timetuple()))
    toAddress = inboxMessages['inboxMessages'][msgID]['toAddress'] + '@bm.addr'
    fromAddress = inboxMessages['inboxMessages'][msgID]['fromAddress'] + '@bm.addr'

    ##Disabled to support new chan format
    #if 'Broadcast' in toAddress:
    #  toAddress = fromAddress

    subject = inboxMessages['inboxMessages'][msgID]['subject'].decode('base64')
    body = inboxMessages['inboxMessages'][msgID]['message'].decode('base64')
    return dateTime, toAddress, fromAddress, subject, body
    
def listMsgs():
    inboxMessages = _getAll()
    return len(inboxMessages['inboxMessages'])
    
def markForDelete(msgID):
    global purgeList
    inboxMessages = _getAll()
    msgRef = str(inboxMessages['inboxMessages'][msgID]['msgid'])
    purgeList.append(msgRef)
    return 0
    
def cleanup():
    global allMessages
    global purgeList
    while len(purgeList):
      _deleteMessage(purgeList.pop())
    allMessages = []
    return 0

def _deleteMessage(msgRef):
    api = _makeApi(_getKeyLocation())
    api.trashMessage(msgRef) #TODO uncomment this to allow deletion 
    return 0 
    
def getUIDLforAll():
    api = _makeApi(_getKeyLocation())
    inboxMessages = json.loads(api.getAllInboxMessages())
    refdata = []
    for msgID in range(len(inboxMessages['inboxMessages'])):
      msgRef = inboxMessages['inboxMessages'][msgID]['msgid'] #gets the message Ref via the message index number
      refdata.append(str(msgRef))
    return refdata #api.trashMessage(msgRef) #TODO uncomment this to allow deletion
    
def getUIDLforSingle(msgID):
    api = _makeApi(_getKeyLocation())
    inboxMessages = json.loads(api.getAllInboxMessages())
    msgRef = inboxMessages['inboxMessages'][msgID]['msgid'] #gets the message Ref via the message index number
    return [str(msgRef)]


def list_my_addresses():
    api = _makeApi(_getKeyLocation())
    my_addresses = json.loads(api.listAddresses2())[u'addresses']
    for address in my_addresses:
        address[u'label'] = base64.b64decode(address[u'label'])
    return my_addresses


def create_random_address(label):
    label_base64 = base64.b64encode(label)
    eighteen_byte_ripe = True
    total_difficulty = 1
    small_message_difficulty = 1

    api = _makeApi(_getKeyLocation())
    address = api.createRandomAddress(label_base64, eighteen_byte_ripe, total_difficulty, small_message_difficulty)
    return address

##############################################################################

def lookupAppdataFolder(): #gets the appropriate folders for the .dat files depending on the OS. Taken from bitmessagemain.py
    import sys
    APPNAME = "PyBitmessage"
    from os import path, environ
    if sys.platform == 'darwin':
        if "HOME" in environ:
            dataFolder = path.join(os.environ["HOME"], "Library/Application support/", APPNAME) + '/'
        else:
            logging.warning('Could not find home folder, please report this message and your OS X version to the Daemon Github.')
            os.exit()

    elif 'win32' in sys.platform or 'win64' in sys.platform:
        dataFolder = path.join(environ['APPDATA'], APPNAME) + '\\'
    else:
        dataFolder = path.expanduser(path.join("~", "." + "config", APPNAME + "/"))
    return dataFolder
    
def apiData():
    global keysPath
    
    config = ConfigParser.SafeConfigParser()
    keysPath = 'keys.dat'
    config.read(keysPath) #First try to load the config file (the keys.dat file) from the program directory

    try:
        config.get('bitmessagesettings','settingsversion')
        appDataFolder = ''
    except:
        #Could not load the keys.dat file in the program directory. Perhaps it is in the appdata directory.
        appDataFolder = lookupAppdataFolder()
        keysPath = appDataFolder + 'keys.dat'
        config = ConfigParser.SafeConfigParser()
        config.read(keysPath)

        try:
            config.get('bitmessagesettings','settingsversion')
        except:
            #keys.dat was not there either, something is wrong.
            print ' '
            print '******************************************************************'
            print 'There was a problem trying to access the Bitmessage keys.dat file.'
            print '******************************************************************'
            print ' '
            print 'looking for {0} \n'.format(keysPath)
            print '{0}\n'.format(config)

    try:
        apiConfigured = config.getboolean('bitmessagesettings','apienabled') #Look for 'apienabled'
        apiEnabled = apiConfigured
    except:
        apiConfigured = False #If not found, set to false since it still needs to be configured
        print "You need to edit your keys.dat file and enable bitmessage's API"
        print "See for more details: https://bitmessage.org/wiki/API"
        print "Will now crash..."
        raise

    #if (apiConfigured == False):#If the apienabled == false or is not present in the keys.dat file, notify the user and set it up
        #apiInit(apiEnabled) #Initalize the keys.dat file with API information

    #keys.dat file was found or appropriately configured, allow information retrieval
    apiEnabled = config.getboolean('bitmessagesettings','apienabled')
    apiPort = config.getint('bitmessagesettings', 'apiport')
    apiInterface = config.get('bitmessagesettings', 'apiinterface')
    apiUsername = config.get('bitmessagesettings', 'apiusername')
    apiPassword = config.get('bitmessagesettings', 'apipassword')
            
    return "http://" + apiUsername + ":" + apiPassword + "@" + apiInterface+ ":" + str(apiPort) + "/" #Build the api credentials

