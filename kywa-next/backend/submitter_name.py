"""Masked submission names. Raw legacy names are converted only at the read boundary."""
import re
import unicodedata

INITIALS = '㉠ㄲ㉡㉢ㄸ㉣㉤㉥ㅃ㉦ㅆ㉧㉨ㅉ㉩㉪㉫㉬㉭'
MASKED = re.compile(r'[가-힣][㉠-㉭ㄲㄸㅃㅆㅉ]{0,99}')


def is_masked_name(value):
    return isinstance(value, str) and bool(MASKED.fullmatch(value))


def display_name(value):
    """Idempotent; unsupported legacy values fail closed rather than exposing raw text."""
    if not isinstance(value, str):
        return ''
    value = unicodedata.normalize('NFC', re.sub(r'\s+', '', value))
    if is_masked_name(value):
        return value
    if not re.fullmatch(r'[가-힣]{1,100}', value):
        return ''
    return value[0] + ''.join(INITIALS[(ord(c) - 0xAC00) // 588] for c in value[1:])
