import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.config import Settings
from backend.domain import RiskList
from backend.services import AIService, ServiceError, ai_response_schema


@pytest.mark.parametrize('code,message,reason,attempts', [
    (400, 'API key not valid', 'invalid_api_key', 1),
    (403, 'Your API key was reported as leaked', 'blocked_api_key', 1),
    (404, 'model unavailable', 'model_unavailable', 1),
    (403, 'denied', 'permission_denied', 1),
    (429, 'rate limit', 'rate_limited', 3),
    (503, 'unavailable', 'provider_unavailable', 3),
    (400, 'bad schema', 'invalid_request', 1),
])
def test_ai_errors_log_only_safe_reason(monkeypatch, caplog, code, message, reason, attempts):
    from google import genai
    class ProviderError(Exception):
        pass
    error = ProviderError(message + ' secret-test-key private-input-name https://provider?key=secret-test-key')
    error.code = code
    generate = MagicMock(side_effect=error)
    client = MagicMock()
    client.__enter__.return_value = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    monkeypatch.setattr(genai, 'Client', lambda **kwargs: client)
    monkeypatch.setattr('backend.services.time.sleep', lambda seconds: None)
    with caplog.at_level(logging.WARNING, logger='kywa'):
        with pytest.raises(ServiceError) as failure:
            AIService(Settings())._generate('private-input-name', RiskList)
    assert generate.call_count == attempts
    assert f'reason={reason} status={code}' in caplog.text
    assert len(caplog.records) == 1
    for sensitive in ('secret-test-key', 'private-input-name', 'https://provider'):
        assert sensitive not in caplog.text
        assert sensitive not in str(failure.value)


def test_provider_schema_compatibility_keeps_strict_local_validation():
    import json
    from pydantic import ValidationError
    provider_schema = ai_response_schema(RiskList)
    assert 'additionalProperties' not in json.dumps(provider_schema)
    assert RiskList.model_json_schema()['additionalProperties'] is False
    item = dict(category='test', location='test', scenario='test', p=1, s=1, law='', solution='test')
    with pytest.raises(ValidationError):
        RiskList.model_validate({'items': [dict(item, unrequested='value')]})
    with pytest.raises(ValidationError):
        RiskList.model_validate({'items': [item], 'unrequested': 'value'})
