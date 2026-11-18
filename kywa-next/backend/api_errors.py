"""Safe diagnostics for application and upstream failures."""
import logging
import json
import socket
import uuid

import httpx
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from googleapiclient.errors import HttpError

log = logging.getLogger('kywa')


def error_response(request, status, code, detail, retryable=False):
    identifier = getattr(request.state, 'request_id', None) or uuid.uuid4().hex[:16]
    request.state.error_code=code
    return JSONResponse(
        {'detail': detail, 'code': code, 'request_id': identifier, 'retryable': retryable},
        status_code=status,
        headers={'X-Request-ID': identifier, 'Cache-Control': 'private, no-store'},
    )


def unexpected(request, exc):
    if isinstance(exc, HttpError):
        reasons=set()
        try:
            error=json.loads(exc.content[:10000]).get('error',{})
            reasons={item.get('reason','') for item in error.get('errors',[])}
        except (ValueError,TypeError,AttributeError):pass
        if exc.resp.status == 429 or reasons & {'rateLimitExceeded','userRateLimitExceeded','quotaExceeded','dailyLimitExceeded'}:
            response=error_response(request,429,'google_rate_limit',
                'Google 연동 요청 한도에 도달했습니다. 작성 내용은 유지됩니다. 약 1분 후 다시 시도해 주세요.')
            response.headers['Retry-After']='60'
            return response
        if exc.resp.status in (401, 403):
            return error_response(request, 503, 'google_access',
                                  'Google 저장소 접근을 확인하지 못했습니다. 운영 담당자에게 오류번호를 알려주세요.')
        return error_response(request, 503, 'google_unavailable',
                              'Google 저장소 연결이 지연되고 있습니다. 입력을 유지한 채 다시 시도해 주세요.', True)
    if isinstance(exc, (TimeoutError, socket.timeout, httpx.TimeoutException)):
        return error_response(request, 504, 'upstream_timeout',
                              '연결 대기시간을 초과했습니다. 입력을 유지한 채 다시 시도해 주세요.', True)
    if isinstance(exc, (ConnectionError, OSError, httpx.TransportError)):
        return error_response(request, 503, 'upstream_connection',
                              '외부 서비스와 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.', True)
    return error_response(request, 503, 'server_error',
                          '서버가 작업을 완료하지 못했습니다. 입력은 유지됩니다. 오류번호를 운영 담당자에게 알려주세요.', True)


def http_code(exc: HTTPException):
    codes = {401: 'session_expired', 403: 'access_denied', 404: 'not_found',
             409: 'revision_conflict', 413: 'file_size', 422: 'invalid_input',
             429: 'rate_limit', 503: 'service_unavailable', 504: 'timeout'}
    return codes.get(exc.status_code, 'request_failed')
