"""Read old single-photo records and ordered before-photo lists."""


def before_ids(record):
    primary = record.get('photo_id') or ''
    values = record.get('photo_ids') or ([primary] if primary else [])
    return list(dict.fromkeys(value for value in values if value))[:2]


def before_links(record):
    links = record.get('photo_view_urls') or []
    result = []
    for index, file_id in enumerate(before_ids(record)):
        if index < len(links) and links[index]:
            result.append(links[index])
        elif index == 0 and record.get('photo_view_url'):
            result.append(record['photo_view_url'])
        else:
            result.append(f'https://drive.google.com/file/d/{file_id}/view')
    return result


def report_slots(record):
    ids = before_ids(record)
    after = (record.get('after') or {}).get('photo_id') or ''
    if len(ids) == 2:
        slots = [('개선 전 ①', ids[0]), ('개선 전 ②', ids[1])]
        if after:
            slots.append(('개선 후', after))
        return slots
    return [('개선 전', ids[0] if ids else ''), ('개선 후', after)]
