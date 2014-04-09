'''
Created on 7 Mar, 2014

@author: qiren
'''
import log as logging
import threading
import settings
from multiprocessing import Queue
from functools import reduce

logger = logging.getLogger('engine')


def singleton(cls, *args, **kwargs):
    instances = {}
    def _singleton():
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    return _singleton


@singleton
class Router:
    """
    store the messages from vinzor server and forward it to right image
    """
    ROUTE_TABLE = {}
    TEMPLATE_INFO_LIST = ['template_id', 'packages', 'template_name', 'template_is_public',
                          'template_type', 'template_url', 'template_fs', 'template_checksum',
                          'template_source']
    VINZOR_HEADER = ['name', 'device_id', 'pdu', 'request_id', 'code', 'param', 'remote_ip']
    ENGINE_RECV_PACKAGES_KEY = ['name', 'display_name', 'version', 'os_type', 'os_architecture',
                        'checksum', 'install_cmd', 'priority', 'path']
    lock = threading.Lock()

    def __init__(self):
        pass

    def _check(self, data):
        if not set(self.VINZOR_HEADER) ^ set(data.keys()) and \
           not set(self.TEMPLATE_INFO_LIST) ^ set(data['param'].keys()):
            for i in data['param']['packages']:
                if set(self.ENGINE_RECV_PACKAGES_KEY) ^ set(i.keys()):
                    return False
            return True
        return False

    def tmpl_forward(self, template_id):
        logger.debug(self.ROUTE_TABLE)
        if template_id in self.ROUTE_TABLE:
            resp = self.ROUTE_TABLE[template_id].get()
            self.lock.acquire()
            if self.ROUTE_TABLE[template_id].empty():
                logger.info('delete record %s' % template_id)
                del self.ROUTE_TABLE[template_id]
            self.lock.release()
            return resp
        return None

    def tmpl_store(self, data):
        logger.debug(data)
        if self._check(data):
            ss = data['param']['template_id']
            self.lock.acquire()
            data['param'] = data['param']['packages']
            if ss not in self.ROUTE_TABLE:
                self.ROUTE_TABLE[ss] = Queue()
            self.ROUTE_TABLE[ss].put(data)
            self.lock.release()
            return True
        return False


# sys.modules[__name__] = Router()
router = Router()