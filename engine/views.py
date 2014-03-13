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

logger = logging.getLogger('engine')


@csrf_exempt
def query_op(request):
    if request.method == 'POST':
        req = simplejson.loads(request.body.decode())
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
        data = simplejson.loads(request.body.decode())

        req = copy.deepcopy(data)
        try:
            res = router.tmpl_store(data)
        except Exception as ex:
            logger.error(ex)
        else:
            if res:
                logger.info('store request successfully')
                work = worker.Worker(req['param']['template_id'], req['param']['template_type'],
                                     req['param']['template_name'], req['param']['template_is_public'])
                work.start()
                return HttpResponse(simplejson.dumps({'result': 'success'}))
    return HttpResponse(simplejson.dumps({'result': 'fail'}))

