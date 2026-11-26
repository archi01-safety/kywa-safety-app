import pytest
from backend.organization import load_organization
from backend.branding import palette, contrast, mix

BRANDS = {
    'kywa': ('#F0145A','#2A8FD8'), 'fowi': ('#129F4A','#59C2E0'),
    'knps': ('#3B9F49','#257ABA'), 'khidi': ('#F2682A','#78777C'),
    'knf': ('#014099','#E60012'), 'kohi': ('#E24E2C','#F6A12B'),
    'cayf': ('#53805A','#E3B65C'), 'ayf': ('#FCD600','#C81E86'),
}

@pytest.mark.parametrize('identity', BRANDS)
def test_brand_originals_readable_derivatives_and_scope(identity):
    brand = load_organization(identity).branding
    assert (brand.primary,brand.secondary)==BRANDS[identity]
    assert brand.design==('premium' if identity=='kywa' else 'standard')
    for original in BRANDS[identity]:
        colors=palette(original)
        for state in ('button','hover'):
            assert contrast(colors[state],colors['buttonText'])>=4.5
        for bg in ('#181B20','#242830','#2C313B','#101620','#1C2431','#252F3E'):
            assert contrast(colors['darkText'],bg)>=4.5
        for bg in ('#FFFFFF','#F4F4F2','#F0F1F3'):
            assert contrast(colors['lightText'],bg)>=4.5
        # Focus and button boundaries use the same readable accent (minimum 3:1).
        assert contrast(colors['darkText'],'#252F3E')>=3
    if identity=='kywa':
        colors=palette(brand.primary)
        assert contrast(mix(colors['button'],'#FFFFFF',11/255),colors['buttonText'])>=4.5
