import time
import logging
from django.db import connection
from django.utils.deprecation import MiddlewareMixin
from django.utils.encoding import smart_str

logger = logging.getLogger(__name__)


class TimeLogMiddleware(MiddlewareMixin):

    def process_request(self, request):
        # py2.7: DO NOT USE time.clock() - although it is used for benchmarking
        #   time.time() gives more realistic results
        request._start = time.time()

    def process_response(self, request, response):
        # if an exception is occured in a middleware listed
        # before TimeLogMiddleware then request won't have '_start' attribute
        # and the original traceback will be lost (original exception will be
        # replaced with AttributeError)
        response_time = time.time() - request._start

        sqltime = sum([float(q.get('time', 0.0)) for q in connection.queries])

        if hasattr(request, '_start'):
            d = {
                'method': request.method,
                'time': response_time,
                'code': response.status_code,
                'url': smart_str(request.path_info),
                'sql': len(connection.queries),
                'sqltime': sqltime,
            }
            msg = '%(method)s "%(url)s" (%(code)s) %(time).2f (%(sql)dq, %(sqltime).4f)' % d
            logger.info(msg)
        return response
