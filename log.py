################################################################################
#  All Rights Reserves ©2013,Vinzor Co.,Ltd.
#
#  History: 1.Create by Qi Ren at 2013-12-23;
################################################################################

import settings
import logging
import os


def setup_default_config():
    logger = logging.getLogger('engine')
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(os.path.join(settings.LOG_PATH, settings.LOG_FILE_NAME), encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(filename)s %(levelname)s %(lineno)s %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)


def getLogger(name):
    return logging.getLogger(name)


setup_default_config()
