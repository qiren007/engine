'''
Created on 7 Mar, 2014

@author: qiren
'''


from django.http import HttpResponse
from django.utils import simplejson
from django.views.decorators.csrf import csrf_exempt
from router import router
import log as logging
import worker
import copy
import settings

logger = logging.getLogger('engine')


@csrf_exempt
def query_op(request):
    if request.method == 'POST':
        req = simplejson.loads(request.body.decode())
        logger.debug(request.META.get('REMOTE_ADDR'))
        logger.debug(req)
        try:
            resp = router.tmpl_forward(req['template_id'])
            logger.info('query template %s' % req['template_id'])
        except KeyError as ex:
            logger.error(ex)
        else:
            if resp:
                logger.info('%s forward successfully' % req['template_id'])
                return HttpResponse(simplejson.dumps(resp, ensure_ascii=False))
            else:
                logger.info('no such template in route table should forward')
    return HttpResponse(simplejson.dumps({'result': 'fail'}))


@csrf_exempt
def install(request):
    if request.method == 'POST':
        remote_ip = request.META.get('REMOTE_ADDR')
        try:
            data = simplejson.loads(request.body.decode())
        except Exception as ex:
            logger.error(ex)
            return HttpResponse(simplejson.dumps({'result': 'fail'}))
        data['remote_ip'] = 'http://%s:%s' % (remote_ip, settings.SERVER_PORT)
        req = copy.deepcopy(data)
        if router.tmpl_store(data):
            logger.info('store request successfully')
            req['param']['template_url'] = 'http://%s:%s%s' % (remote_ip,
                                                              settings.SERVER_PORT,
                                                              req['param']['template_url'])
            job = worker.MakeTemplate(req['param']['template_id'],
                                      req['param']['template_type'],
                                      req['param']['template_name'],
                                      req['remote_ip'],
                                      src=req['param']['template_source'],
#                                       checksum=req['param']['template_checksum'],
                                      checksum='e32fc383b3a787f5c5b39f5455a539d8',
                                      is_public=req['param']['template_is_public'],
                                      fs=req['param']['template_fs'],
                                      remote_image_path=req['param']['template_url'],
                                      worker=worker.engine_thr_pool)
            worker.engine_thr_pool.add_job('make_tmpl', job.do_job)
            return HttpResponse(simplejson.dumps({'result': 'success'}))
    return HttpResponse(simplejson.dumps({'result': 'fail'}))

