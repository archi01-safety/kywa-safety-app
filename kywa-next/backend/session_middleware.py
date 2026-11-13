"""Avoid stale read responses overwriting a newer signed login cookie."""
import copy
from starlette.middleware.sessions import SessionMiddleware


class StableSessionMiddleware(SessionMiddleware):
    def __init__(self,app,**kwargs):
        async def capture(scope,receive,send):
            scope['_kywa_initial_session']=copy.deepcopy(scope.get('session',{}))
            await app(scope,receive,send)
        super().__init__(capture,**kwargs)

    async def __call__(self,scope,receive,send):
        async def only_changed(message):
            if (message['type']=='http.response.start'
                    and scope.get('_kywa_initial_session')==scope.get('session')):
                prefix=(self.session_cookie+'=').encode()
                message={**message,'headers':[(key,value) for key,value in message.get('headers',[])
                    if not (key.lower()==b'set-cookie' and value.startswith(prefix))]}
            await send(message)
        await super().__call__(scope,receive,only_changed)
