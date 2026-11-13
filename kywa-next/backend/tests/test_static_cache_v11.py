"""The rendered shell revalidates across deployments; protected API data never caches."""
import json

import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend import main


@pytest.mark.parametrize('prefix,strip', [('',False),('/apps/kywa-safety',False),('/apps/kywa-safety',True)])
def test_deployed_shell_revalidates_including_conditional_and_ax_requests(tmp_path,monkeypatch,prefix,strip):
    root=tmp_path/'app';static=root/'frontend'/'out';static.mkdir(parents=True)
    html=static/'index.html';html.write_text('<html>first deployment</html>',encoding='utf-8')
    (static/'build-config.json').write_text(json.dumps({'basePath':prefix,'format':1}))
    chunk=static/'_next'/'static'/'chunks'/'content-hash.js';chunk.parent.mkdir(parents=True)
    chunk.write_text('/* hashed bundle */')
    monkeypatch.setattr(main,'ROOT',root)
    cfg=Settings(_env_file=None,app_base_url='http://testserver',app_base_path=prefix,
                 demo_data_path=str(tmp_path/'data.json'),app_data_dir=str(tmp_path/'data'))
    app=main.create_app(cfg)
    class Strip:
        async def __call__(self,scope,receive,send):
            if scope['type']=='http' and prefix and scope['path'].startswith(prefix):
                scope=dict(scope,path=scope['path'][len(prefix):] or '/',raw_path=scope['raw_path'][len(prefix):] or b'/')
            await app(scope,receive,send)
    with TestClient(Strip() if strip else app) as client:
        first=client.get(prefix+'/')
        assert first.status_code==200 and 'first deployment' in first.text
        policy='no-cache, max-age=0, must-revalidate'
        assert first.headers['cache-control']==policy
        etag=first.headers['etag']
        same=client.get(prefix+'/',headers={'If-None-Match':etag})
        assert same.status_code==304 and same.headers['cache-control']==policy
        html.write_text('<html>second deployment with a new bundle</html>',encoding='utf-8')
        updated=client.get(prefix+'/',headers={'If-None-Match':etag})
        assert updated.status_code==200 and 'second deployment' in updated.text
        assert updated.headers['cache-control']==policy
        assert client.get(prefix+'/index.html').headers['cache-control']==policy
        assert client.get(prefix+'/_next/static/chunks/content-hash.js').headers['cache-control']=='public, max-age=31536000, immutable'
        assert client.get(prefix+'/api/bootstrap').headers['cache-control']=='no-store'
        assert client.get(prefix+'/healthz').headers['cache-control']=='no-store'
