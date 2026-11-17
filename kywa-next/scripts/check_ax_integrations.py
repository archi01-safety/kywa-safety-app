"""Run on the AX server to check all live integrations without writing evaluations."""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description='AX 실연동 확인. 평가/사진 저장 없이 권한·헤더·API 응답 검사. AI 소량 호출 포함.')
    parser.add_argument('--config',type=Path,help='배포 폴더 밖의 비공개 .env 파일. 미지정 시 APP_ENV_FILE 또는 서버 환경변수 사용.')
    args=parser.parse_args()
    from backend.ax_config import configure_ax_environment
    from dotenv import dotenv_values
    if args.config:
        if not args.config.is_absolute() or args.config.resolve().is_relative_to(ROOT) or not args.config.is_file():
            parser.error('--config에 배포 폴더 밖의 실제 설정파일 절대 경로를 지정하세요.')
        os.environ['APP_ENV_FILE']=str(args.config)
    try:
        configure_ax_environment(ROOT)
        from backend.config import Settings
        from backend.ax_integrations import check_integrations
        config={}
        filename=os.environ.get('APP_ENV_FILE')
        if filename:
            for key,value in dotenv_values(filename,encoding='utf-8-sig',interpolate=False).items():
                if key.lower() in Settings.model_fields and value is not None:
                    config[key.lower()]=os.environ.get(key,value)
        result=check_integrations(Settings(_env_file=None,**config))
    except Exception:
        result={'all_passed':False,'code':'invalid_server_configuration',
            'action':'실연동 모드와 필수 API/Google/PIN 설정, 운영 저장소 사용 설정을 확인하세요. 인증값은 로그에 출력하지 마세요.'}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['all_passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
