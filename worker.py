'''
Created on 8 Mar, 2014

@author: qiren
'''

import threading
import settings
import os
import utils
import shutil
from queue import Queue
from router import router
import log as logging

logger = logging.getLogger('engine')


class MakeTemplate:
    TMPL_SRC = ['std_img', 'openstack_img', 'openstack_snapshot']
    def __init__(self, template_id, image_type, image_name, remote_ip, src='std_img',
                 checksum=None, is_public=True, fs=None, remote_image_path=None, worker=None):
        """
        @param template_id: use for identify the image, here we use the name of the image in std
                            image warehouse
        @param image_type: use for identify which os of the image has
        @param image_name: set the name of image after upload to cloud
        @param is_public: the option to set the image is public 
        """
        self.image_type = image_type
        self.image_name = image_name
        self.is_public = is_public
        self.template_id = template_id
        self.remote_ip = remote_ip
        self.checksum = checksum
        self.fs = fs
        self.src = src if src in  MakeTemplate.TMPL_SRC else 'std_img'
        self.remote_image_path = remote_image_path
        self.path = None
        self.worker = worker
        self.image_handler = None
        self.kvm_tool = utils.KvmTool()
        self.gs = utils.GlanceService()
 
    def _get_img_from_repository(self):
        if self.remote_image_path and self.src == 'std_img' and \
            utils.download(self.remote_image_path, settings.LOCAL_IMAGE_WAREHOUSE, self.template_id):
            return True
        elif self.src != 'std_img' and \
            self.gs.download(self.template_id, os.path.join(settings.LOCAL_IMAGE_WAREHOUSE, self.template_id)):
            return True
        return False
 
    def _select_img(self):
        if self.checksum is None: return None
        tmpl = os.path.join(settings.LOCAL_IMAGE_WAREHOUSE, self.template_id)
        if not os.path.isfile(tmpl):
            i = settings.MAX_TRY_DOWNLOAD_IMAGE_TIME
            logger.info('start to get image from repository')
            while not self._get_img_from_repository():
                i -= 1
                if i == 0:
                    logger.info('fail to get image, clean temporary download file')
                    utils.clean_tmp_file(tmpl)
                    return None
            logger.info('get image successfully, start to check integrity...')
            if not utils.check_integrity(tmpl, self.checksum):
                logger.error('check integrity: fail, clean broken image...')
                utils.clean_tmp_file(tmpl)
                return None
            logger.info('check integrity: pass')
        count = 0
        while os.path.isfile(os.path.join(settings.TEMP, str(count) + '_' + self.image_name)):
            count += 1
        tmp_name = os.path.join(settings.TEMP, str(count) + '_' + self.image_name)
        logger.info('start to create temporary file %s' % tmp_name)
        try:
            shutil.copy2(tmpl, os.path.join(settings.TEMP, tmp_name))
        except Exception as ex:
            logger.error(ex)
            return None
        return count
 
    def make_tmpl(self):
        logger.info('start to select image of %s' % self.template_id)
        ret = False
        count = self._select_img()
        if count is not None:
            path = os.path.join(settings.TEMP, str(count) + '_' + self.image_name)
            logger.info('start to inject data to image...')
            img_os_type = 'nt' if self.image_type in settings.OS_FAMILY['nt'] else 'posix'
            self.image_handler = utils.ImgHandler(path, self.fs, self.template_id, img_os_type)
            data = router.tmpl_forward(self.template_id)
            self.image_handler.inject_data_to_vm(data)
            logger.info('start to launch image %s in %s' % (self.image_name, settings.TEMP))
            res = self.kvm_tool.launch(self.image_type, path)
            if res[0]:
                logger.info('create image successfully')
                self.path = path
                ret = True
        return ret

    def upload_tmpl(self):
        if self.path:
            logger.info('start to upload to cloud')
            if self.gs.create(self.path, self.image_name, self.is_public):
                logger.info('upload %s successfully' % self.image_name)
            else:
                logger.error('fail to upload image: %s' % self.image_name)
            logger.info('clean temporary image %s' % self.path)
            utils.clean_tmp_file(self.path)

    def do_job(self):
        if self.make_tmpl() and self.worker:
            self.worker.add_job('upload_tmpl', self.upload_tmpl)
        if self.image_handler:
            self.image_handler.resource_grabber()
        if self.kvm_tool:
            self.kvm_tool.resource_grabber()
        logger.info('finish')


class WorkerManager:
    def __init__(self, max_job_num, *args):
        self.groups = {}
        for name, number in list(args):
            self.groups[name] = (number, [], Queue(max_job_num), Queue(max_job_num))

    def init_pool(self):
        for group in self.groups:
            number, thrs, in_que, out_que = self.groups[group]
            for i in range(number):
                worker_thr = WorkerThread(group, in_que, out_que)
                logger.info('init thread id=%d, owned by group \"%s\"' % (worker_thr.ident, group))
                thrs.append(worker_thr)

    def add_job(self, groupname, func, *args, **kwargs):
        self.groups[groupname][2].put((func, list(args), dict(kwargs)))

    def close_pool(self):
        for i in self.groups:
            self.groups[i][2].join()
            map(lambda x: x.close(), self.groups[i][1])

class WorkerThread(threading.Thread):
    def __init__(self, group, input_queue, output_queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = group
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.active = True
        self.daemon = True
        self.start()

    def close(self):
        self.active = False

    def run(self):
        while self.active:
            func, args, kwargs = self.input_queue.get()
            logger.info('thread %d accept task, owned by group \"%s\"' % (self.ident, self.group))
            self.output_queue.put(func(*args, **kwargs))
            self.input_queue.task_done()
        return


class EngineThreadPool:
    _instance = None

    def __init__(self, max_job_num, *args):
        if not EngineThreadPool._instance:
            EngineThreadPool._instance = WorkerManager(max_job_num, *args)

    def __getattr__(self, attr):
        return getattr(self._instance, attr)

    def __setattr__(self, attr, val):
        return setattr(self._instance, attr, val)


engine_thr_pool = EngineThreadPool(settings.MAX_INPUT_QUEUE_SIZE,
                                   ('make_tmpl', settings.MAKE_TMPL_THR_NUM),
                                   ('upload_tmpl', settings.UPLOAD_TMPL_THR_NUM))
