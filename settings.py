'''
Created on 7 Mar, 2014

@author: qiren
'''

import os

ENGINE_HOME = os.path.abspath(os.path.dirname(__file__))

TOOLS_PATH = os.path.join(ENGINE_HOME, 'tools')

LOG_PATH = os.path.join(ENGINE_HOME, 'log')

LOG_FILE_NAME = os.path.join(LOG_PATH, 'engine.log')

LOCAL_IMAGE_WAREHOUSE = os.path.join(ENGINE_HOME, 'local_image_warehouse')

TEMP = os.path.join(ENGINE_HOME, 'temp')

OS_FAMILY = ['windows 7', 'ubuntu']

VINZOR_HEADER = ['name', 'device_id', 'pdu', 'request_id', 'code', 'param']
ENGINE_RECV_PACKAGES_KEY = ['name', 'display_name', 'version', 'os_type', 'os_architecture',
                        'checksum', 'install_cmd', 'priority', 'path']

# change this url to your server
SERVER_URL = '192.168.0.132:8000'

SERVER_URL_PATH = '/api/agent/make_template/'

TIMEOUT = 3600

IS_PUBLIC = True
CONTAINER_FORMAT = 'ovf'
DISK_FORMAT='qcow2'
MIN_RAM = 2048
MIN_DISK = 20

OS_USERNAME = 'admin'
OS_PASSWORD = 'sysuadmin'
OS_TENANT_NAME = 'demo'
OS_URL = '192.168.0.195'
OS_AUTH_PORT = 5000
OS_AUTH_URL = 'http://192.168.0.195:5000/v2.0'
OS_IMAGE_URL = 'http://192.168.0.195:9292/'