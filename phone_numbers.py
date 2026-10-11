"""Local phone formatting. Preserve incomplete/ambiguous input; never guess digits."""
import re
import phonenumbers as phone

DEFAULT_COUNTRY='US'
REGIONS=set(phone.SUPPORTED_REGIONS)|{'ZZ'}

def country(value,default=DEFAULT_COUNTRY):
    region=value or default
    if not isinstance(region,str) or region not in REGIONS:raise ValueError('Choose a supported phone country code.')
    return region

def countries():return [{'country':r,'calling_code':str(phone.country_code_for_region(r))} for r in sorted(phone.SUPPORTED_REGIONS)]+[{'country':'ZZ','calling_code':''}]

def format_phone(value,region=DEFAULT_COUNTRY,typing=False):
    region=country(region)
    if not isinstance(value,str) or len(value)>80 or any(ord(c)<32 or ord(c)==127 for c in value):raise ValueError('Enter a phone number up to 80 characters without line breaks.')
    value=value.strip();result=dict(value=value,country=region,e164='',extension='',possible=False)
    if not value:return result
    # Combined numbers and arbitrary prose must remain untouched.
    if re.search(r'[/,]|\b(?:or|and)\b',value,re.I):return result
    numeric=re.sub(r'\s*(?:ext\.?|extension|x|#)\s*\d+\s*$','',value,flags=re.I)
    if not re.fullmatch(r'[+\d\s().-]+',numeric):return result
    try:
        parsed=phone.parse(value,None if value.startswith('+') or region=='ZZ' else region)
        if phone.is_possible_number_with_reason(parsed)==phone.ValidationResult.IS_POSSIBLE:
            detected=phone.region_code_for_number(parsed)
            result.update(value=phone.format_number(parsed,phone.PhoneNumberFormat.INTERNATIONAL),country=detected if detected in REGIONS else ('ZZ' if phone.region_code_for_country_code(parsed.country_code)=='001' else region),e164=phone.format_number(parsed,phone.PhoneNumberFormat.E164),extension=parsed.extension or '',possible=True)
    except phone.NumberParseException:pass
    if typing:
        # As-you-type formatting is applied only to numeric input (extensions stay intact).
        if re.fullmatch(r'[+\d\s().-]+',value):
            formatter=phone.AsYouTypeFormatter(region);formatted=''
            for char in value:
                if char.isdigit() or char=='+':formatted=formatter.input_digit(char)
            result['value']=formatted or value
        else:result['value']=value
    return result

def normalize_fields(body,keys,default=DEFAULT_COUNTRY):
    for key in keys:
        if key not in body:continue
        selected=country(body.get(key+'_country'),default)
        formatted=format_phone(body[key] if body[key] is not None else '',selected)
        body[key]=formatted['value'];body[key+'_country']=formatted['country']
    return body
