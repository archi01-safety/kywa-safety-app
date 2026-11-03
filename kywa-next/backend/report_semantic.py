"""Shared, normalized report photos and semantic (paragraph based) HWPX."""
import base64
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
from PIL import Image, ImageDraw, ImageOps
from .chart_colors import CATEGORY_COLOR_MAP, FALLBACK_COLOR
from .services import ServiceError


class ReportError(ServiceError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class Photos:
    def __init__(self, records, store):
        self.data = {}
        self.keys = []
        for record in records:
            pair = [record.get('photo_id') or '', (record.get('after') or {}).get('photo_id') or '']
            self.keys.append(pair)
            for key in pair:
                if not key or key in self.data:
                    continue
                try:
                    raw = store.get(key)
                    with Image.open(io.BytesIO(raw)) as image:
                        image = ImageOps.exif_transpose(image).convert('RGB')
                        image.thumbnail((1100, 1100))
                        out = io.BytesIO()
                        image.save(out, 'JPEG', quality=90)
                        self.data[key] = out.getvalue()
                except Exception:
                    raise ReportError('photo', '보고서 사진을 불러오지 못했습니다. 다시 시도해 주세요.') from None

    def get(self, key):
        return self.data[key]


def chart(categories):
    image = Image.new('RGB', (500, 500), 'white')
    draw = ImageDraw.Draw(image)
    angle, total = -90, sum(categories.values())
    for name, count in categories.items():
        end = angle + 360 * count / total
        draw.pieslice((4, 4, 496, 496), angle, end,
                      fill=CATEGORY_COLOR_MAP.get(name, FALLBACK_COLOR), outline='white', width=3)
        angle = end
    out = io.BytesIO()
    image.save(out, 'PNG')
    return out.getvalue()


def hwpx(model, photos):
    from .report_layout import wrapped
    # Estimate flow heights before serialization. Do not silently clip/scale text.
    for detail in model['details']:
        lines = sum(len(wrapped(label + '  ' + (detail['summary'][key] or '기록 없음'), 523, 9.5))
                    for label, key in [('위험상황', 'scenario'), ('감소대책', 'solution'), ('실제 조치', 'action'), ('관련근거', 'law')])
        if lines > 12 or len(wrapped(detail['before']['location'], 523, 11)) > 2:
            raise ReportError('layout', '한글 문서의 세부 내용이 배치 한도를 넘었습니다. 요약을 다시 생성해 주세요.')
    node = os.environ.get('REPORT_NODE') or shutil.which('node')
    if not node:
        candidates = list((Path(__file__).resolve().parents[2] / '.tools/node-runtime').glob('*/node.exe'))
        node = str(candidates[0]) if candidates else None
    if not node:
        raise ReportError('runtime', '한글 보고서 실행 환경이 준비되지 않았습니다.')
    payload = {'model': model, 'photos': {k: base64.b64encode(v).decode() for k, v in photos.data.items()},
               'photoKeys': photos.keys, 'chart': base64.b64encode(chart(model['facts']['categories'])).decode(),
               'colors': CATEGORY_COLOR_MAP}
    try:
        result = subprocess.run([node, str(Path(__file__).parent / 'assets/hwpx-semantic.cjs')],
                                input=json.dumps(payload, ensure_ascii=False).encode(), capture_output=True,
                                timeout=90, check=True)
        if not result.stdout.startswith(b'PK'):
            raise ValueError()
        return result.stdout
    except Exception:
        raise ReportError('document', '편집 가능한 한글 문서 구성에 실패했습니다. 다시 생성해 주세요.') from None
