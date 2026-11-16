"""JPEG filenames/MIME variants use the same content-validated pipeline in every institution."""
import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from backend.config import Settings
from backend.main import create_app

ORGS=('kywa','ayf','fowi','khidi','knps','knf','kohi','cayf')


@pytest.mark.parametrize('organization',ORGS)
@pytest.mark.parametrize('filename,mime,progressive,orientation',[
    ('IMG_0001.jpg','image/jpeg',False,1),
    ('IMG_0001.jpeg','image/jpeg',False,1),
    ('IMG_0001.JPEG','application/octet-stream',False,1),
    ('현장.JpEg','',True,6),
    ('IMG_0001.jpeg','image/pjpeg',True,6),
])
def test_jpeg_prepare_and_preview(organization,filename,mime,progressive,orientation,tmp_path):
    cfg=Settings(_env_file=None,organization_id=organization,app_env='demo',
        app_base_url='http://testserver',demo_data_path=str(tmp_path/'records.json'))
    raw=io.BytesIO();exif=Image.Exif();exif[274]=orientation;exif[315]='synthetic metadata to remove'
    Image.new('RGB',(120,80),'#40586e').save(raw,'JPEG',progressive=progressive,exif=exif)
    with TestClient(create_app(cfg),base_url=cfg.app_base_url) as client:
        boot=client.get('/api/bootstrap').json()
        client.headers.update({'Origin':cfg.app_base_url,'X-CSRF-Token':boot['csrf']})
        response=client.post('/api/photos/prepare',files={'photo':(filename,raw.getvalue(),mime)})
        assert response.status_code==200,response.text
        preview=client.get(response.json()['url'])
        assert preview.status_code==200 and preview.headers['content-type']=='image/jpeg'
        image=Image.open(io.BytesIO(preview.content))
        assert image.format=='JPEG' and image.mode=='RGB'
        assert image.size==((80,120) if orientation==6 else (120,80))
        assert not image.getexif()


@pytest.mark.parametrize('organization',ORGS)
@pytest.mark.parametrize('frames',[2,8])
def test_multi_picture_jpeg_uses_primary_still_only(organization,frames,tmp_path):
    cfg=Settings(_env_file=None,organization_id=organization,app_env='demo',
        app_base_url='http://testserver',demo_data_path=str(tmp_path/'records.json'))
    raw=io.BytesIO()
    Image.new('RGB',(120,80),'#dd4422').save(raw,'MPO',save_all=True,
        append_images=[Image.new('RGB',(120,80),'#2233dd') for _ in range(frames-1)])
    source=Image.open(io.BytesIO(raw.getvalue()))
    assert source.format=='MPO' and source.n_frames==frames and raw.getvalue().startswith(b'\xff\xd8')
    with TestClient(create_app(cfg),base_url=cfg.app_base_url) as client:
        boot=client.get('/api/bootstrap').json()
        client.headers.update({'Origin':cfg.app_base_url,'X-CSRF-Token':boot['csrf']})
        response=client.post('/api/photos/prepare',files={'photo':('IMG_LIVE.jpeg',raw.getvalue(),'image/jpeg')})
        assert response.status_code==200,response.text
        preview=client.get(response.json()['url'])
        image=Image.open(io.BytesIO(preview.content))
        assert image.format=='JPEG' and getattr(image,'n_frames',1)==1
        assert image.size==(120,80) and image.getpixel((60,40))[0]>image.getpixel((60,40))[2]
        assert 'mp' not in image.info and not image.getexif()


@pytest.mark.parametrize('kind',['corrupt','GIF','SVG','MOV'])
def test_jpeg_name_and_mime_do_not_bypass_content_validation(kind,tmp_path):
    cfg=Settings(_env_file=None,app_base_url='http://testserver',demo_data_path=str(tmp_path/'records.json'))
    if kind=='GIF':
        raw=io.BytesIO();Image.new('RGB',(20,20),'blue').save(raw,'GIF');data=raw.getvalue()
    else:
        data={'corrupt':b'not an image','SVG':b'<svg xmlns="http://www.w3.org/2000/svg"/>',
              'MOV':b'\x00\x00\x00\x18ftypqt  \x00\x00\x00\x00qt  \x00\x00\x00\x00'}[kind]
    with TestClient(create_app(cfg),base_url=cfg.app_base_url) as client:
        boot=client.get('/api/bootstrap').json()
        client.headers.update({'Origin':cfg.app_base_url,'X-CSRF-Token':boot['csrf']})
        response=client.post('/api/photos/prepare',files={'photo':('fake.jpeg',data,'image/jpeg')})
        assert 400<=response.status_code<500
        assert 'id' not in response.json()
