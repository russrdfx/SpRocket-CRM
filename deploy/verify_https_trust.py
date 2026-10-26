"""Fail the image build if urllib still trusts compromised eMudhra certificates.

Uses the same standard-library HTTPS client as the hosted Google integration.
Network failures are not accepted as proof of certificate rejection.
"""

import ssl
from urllib.error import URLError
from urllib.request import urlopen


COMPROMISED_ENDPOINTS = (
    'https://dv-g3b-emudhra.we-have-a-problem.com/',
    'https://dv-g3b-aaa-emudhra.we-have-a-problem.com/',
)


def verify_https_trust():
    # Check normal trust first, so an empty/broken CA store cannot pass.
    with urlopen('https://www.python.org/', timeout=20) as response:
        if response.status != 200:
            raise RuntimeError('HTTPS positive control did not return HTTP 200')
    for endpoint in COMPROMISED_ENDPOINTS:
        try:
            with urlopen(endpoint, timeout=20):
                pass
        except URLError as error:
            if isinstance(error.reason, ssl.SSLCertVerificationError):
                print('Rejected compromised certificate:', endpoint)
                continue
            raise RuntimeError('Certificate rejection could not be verified: ' + endpoint) from error
        raise RuntimeError('Compromised certificate was accepted: ' + endpoint)
    print('Outbound HTTPS trust checks passed')


if __name__ == '__main__':
    verify_https_trust()
