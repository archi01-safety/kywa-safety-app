"""Accessible role colors derived from an institution's supplied brand color."""
def rgb(color):
    return tuple(int(color[i:i+2], 16) for i in (1, 3, 5))


def mix(color, target, amount):
    return '#' + ''.join(f'{round(a+(b-a)*amount):02X}' for a,b in zip(rgb(color),rgb(target)))


def luminance(color):
    channels = [v/255 for v in rgb(color)]
    return sum(w*(v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4)
               for w,v in zip((.2126,.7152,.0722),channels))


def contrast(a,b):
    hi,lo = sorted((luminance(a),luminance(b)), reverse=True)
    return (hi+.05)/(lo+.05)


def readable(color, backgrounds, target):
    for step in range(101):
        result = mix(color, target, step/100)
        if all(contrast(result,bg) >= 4.5 for bg in backgrounds):
            return result
    raise ValueError('읽을 수 있는 기관 강조색을 만들 수 없습니다.')


def palette(base):
    if base.upper() == '#ED174F':
        return dict(original=base, button='#C91546', buttonText='#FFFFFF', hover='#AA103A',
                    darkText='#FF6B91', lightText='#B6103D')
    hover = mix(base, '#000000', .10)
    text = max(('#FFFFFF','#101418'), key=lambda c: min(contrast(c,base),contrast(c,hover)))
    # For middle luminances choose a lighter hover if a dark hover would break text contrast.
    if min(contrast(text,base),contrast(text,hover)) < 4.5:
        hover = mix(base, '#FFFFFF' if text == '#101418' else '#000000', .10)
    return dict(original=base,button=base,buttonText=text,hover=hover,
                darkText=readable(base, ['#181B20','#242830','#2C313B',mix(base,'#242830',.88)], '#FFFFFF'),
                lightText=readable(base, ['#FFFFFF','#F4F4F2','#F0F1F3',mix(base,'#FFFFFF',.92)], '#000000'))
