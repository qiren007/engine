'''
Created on 7 Mar, 2014

@author: qiren
'''

import os

ENGINE_HOME = os.path.abspath(os.path.dirname(__file__))

TOOLS_PATH = os.path.join(ENGINE_HOME, 'tools')

LOG_PATH = os.path.join(ENGINE_HOME, 'log')

LOG_FILE_NAME = os.path.join(LOG_PATH, 'engine.log')
DOWNLOAD_FILE_NAME = os.path.join(LOG_PATH, 'download.log')

LOCAL_IMAGE_WAREHOUSE = os.path.join(ENGINE_HOME, 'local_image_repository')

TEMP = os.path.join(ENGINE_HOME, 'temp')

OS_WINDOWS_7 = 'windows 7'
OS_UBUNTU = 'ubuntu'
OS_FAMILY = {'nt':[OS_WINDOWS_7], 'posix':[OS_UBUNTU]}

# change this url to your server
SERVER_PORT = 80

SERVER_URL_PATH = '/api/agent/make_template/'

AGENT_VM_ID_KEY='VM_ID_FOR_IMAGE'
AGENT_DIR_NAME = 'agent'
AGENT_SETTINGS = 'settings.py'
AGENT_DB_NAME = 'db'
AGENT_INFO_FROM_ENGINE_FILENAME = 'data.db'

TIMEOUT = 3600

MAX_TRY_DOWNLOAD_IMAGE_TIME = 3

MAKE_TMPL_THR_NUM = 3

UPLOAD_TMPL_THR_NUM = 5
# the input queue size in engine pool
MAX_INPUT_QUEUE_SIZE = 100

IS_PUBLIC = True
CONTAINER_FORMAT = 'ovf'
DISK_FORMAT='qcow2'
MIN_RAM = 2048
MIN_DISK = 20

OS_USERNAME = 'admin'
OS_PASSWORD = 'sysuadmin'
OS_TENANT_NAME = 'demo'
OS_URL = '192.168.0.215'
OS_AUTH_PORT = 5000
OS_AUTH_URL = 'http://192.168.0.215:5000/v2.0'
OS_IMAGE_URL = 'http://192.168.0.215:9292/'
