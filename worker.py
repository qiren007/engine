'''
Created on 8 Mar, 2014

@author: qiren
'''

import threading
import settings
import os
from utils import GlanceService, KvmTool
import shutil
import log as logging

logger = logging.getLogger('engine')


class Worker(threading.Thread):
    __count = 0
    __lock = threading.Lock()

    def __init__(self, template_id, image_type, image_name, is_public=True, *args, **kwargs):
        """
        @param template_id: use for identify the image, here we use the name of the image in std
                            image warehouse
        @param image_type: use for identify which os of the image has
        @param image_name: set the name of image after upload to cloud
        @param is_public: the option to set the image is public 
        """
        threading.Thread.__init__(self, *args, **kwargs)
        self.image_type = image_type
        self.image_name = image_name
        self.is_public = is_public
        self.template_id = template_id
        self.count_num = -1

    def select_img(self):
        tmpl = os.path.join(settings.LOCAL_IMAGE_WAREHOUSE, self.template_id)
        if os.path.isfile(tmpl):
            tmp_name = str(Worker.__count) + '_' + self.image_name
            if not os.path.isfile(os.path.join(settings.TEMP, tmp_name)):
                shutil.copy2(tmpl, os.path.join(settings.TEMP, tmp_name))
            self.count_num = Worker.__count
            Worker.__lock.acquire()
            Worker.__count += 1
            Worker.__lock.release()
            return Worker.__count
        return None

    def clean_tmp_img(self):
        path = os.path.join(settings.TEMP, str(self.count_num) + '_' + self.image_name)
        if os.path.isfile(path):
            shutil.rmtree(path)

    def run(self):
        logger.info('start to select image of %s' % self.template_id)
        self.select_img()
        if self.count_num != -1:
            path = os.path.join(settings.TEMP, str(self.count_num) + '_' + self.image_name)
            logger.info('start to launch image %s in %s' % (self.image_name, settings.TEMP))
            res = KvmTool.launch(self.image_type, path)
            if res[0]:
                logger.info('create image successfully, start to upload to cloud')
                gs = GlanceService(path, self.image_name, self.is_public)
                if gs.create():
                    logger.info('upload %s successfully' % self.image_name)
                    self.clean_tmp_img()
                else:
                    logger.error('fail to create image: %s' % self.image_name)
                #code here to notify server create image successfully
        #  code here to notify server fail to create image
        