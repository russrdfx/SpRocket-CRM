import ssl
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from deploy.verify_https_trust import verify_https_trust


class HttpsTrustCheck(unittest.TestCase):
    def positive_response(self):
        response = MagicMock()
        response.__enter__.return_value.status = 200
        return response

    @patch('deploy.verify_https_trust.urlopen')
    def test_only_certificate_rejection_passes(self, urlopen):
        rejected = URLError(ssl.SSLCertVerificationError(1, 'certificate verify failed'))
        urlopen.side_effect = [self.positive_response(), rejected, rejected]
        verify_https_trust()
        self.assertEqual(urlopen.call_count, 3)

    @patch('deploy.verify_https_trust.urlopen')
    def test_accepted_compromised_certificate_fails(self, urlopen):
        urlopen.side_effect = [self.positive_response(), self.positive_response()]
        with self.assertRaisesRegex(RuntimeError, 'was accepted'):
            verify_https_trust()

    @patch('deploy.verify_https_trust.urlopen')
    def test_network_failure_is_not_certificate_rejection(self, urlopen):
        urlopen.side_effect = [self.positive_response(), URLError('connection timed out')]
        with self.assertRaisesRegex(RuntimeError, 'could not be verified'):
            verify_https_trust()

    @patch('deploy.verify_https_trust.urlopen')
    def test_http_error_still_means_certificate_was_accepted(self, urlopen):
        urlopen.side_effect = [self.positive_response(), HTTPError('https://example.test', 403, 'Forbidden', {}, None)]
        with self.assertRaises(RuntimeError):
            verify_https_trust()

    @patch('deploy.verify_https_trust.urlopen')
    def test_broken_normal_trust_fails(self, urlopen):
        urlopen.side_effect = URLError(ssl.SSLCertVerificationError(1, 'certificate verify failed'))
        with self.assertRaises(URLError):
            verify_https_trust()


if __name__ == '__main__':
    unittest.main()
