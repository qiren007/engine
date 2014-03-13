'''
Created on 7 Mar, 2014

@author: qiren
'''
import log as logging
import threading
import settings
from multiprocessing import Queue

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
    ROUTE_TABLE = {'win7_32_20G_dev_base.img', }
    __lock = threading.Lock()

    def __init__(self):
        pass

    def _check(self, data):
        for i in settings.VINZOR_HEADER:
            if i not in data:
                return False
        if 'template_id' in data['param'] and 'packages' in data['param'] and \
            'template_name' in data['param'] and 'template_is_public' in data['param'] and \
            'template_type' in data['param']:
            for i in settings.ENGINE_RECV_PACKAGES_KEY:
                for j in data['param']['packages']:
                    if i not in j:
                        return False
            return True
        return False

    def tmpl_forward(self, template_id):
        logger.debug(template_id)
        logger.debug(self.ROUTE_TABLE)
        if template_id in self.ROUTE_TABLE:
            resp = self.ROUTE_TABLE[template_id].get()
            Router.__lock.acquire()
            if self.ROUTE_TABLE[template_id].empty():
                del self.ROUTE_TABLE[template_id]
            Router.__lock.release()
            return resp
        return None

    def tmpl_store(self, data):
        if self._check(data):
            ss = data['param']['template_id']
            Router.__lock.acquire()
            del data['param']['template_id']
            del data['param']['template_name']
            del data['param']['template_type']
            del data['param']['template_is_public']
            data['param'] = data['param']['packages']
            if ss not in self.ROUTE_TABLE:
                self.ROUTE_TABLE[ss] = Queue()
            self.ROUTE_TABLE[ss].put(data)
            Router.__lock.release()
            return True
        return False


# sys.modules[__name__] = Router()
router = Router()