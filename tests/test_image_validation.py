# SPDX-License-Identifier: MIT
"""Reject corrupt boot-image envelopes before any deployment workflow uses them."""
import importlib.util
from pathlib import Path
import struct
import unittest

script = Path(__file__).resolve().parents[1]/'scripts/verify-boot-bundle.py'
spec = importlib.util.spec_from_file_location('verify',script)
verify=importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)
class ImageEnvelopeTests(unittest.TestCase):
    def test_truncated_footer(self):
        with self.assertRaisesRegex(ValueError,'Truncated'):
            verify.original_image(b'AVBf')
    def test_footer_cannot_point_beyond_partition(self):
        footer=struct.pack('>4sIIQQQ28s',b'AVBf',1,0,4096,4096,8192,bytes(28))
        with self.assertRaisesRegex(ValueError,'ranges'):
            verify.original_image(bytes(4096)+footer)
    def test_random_image_not_boot(self):
        with self.assertRaisesRegex(ValueError,'header'):
            verify.inspect_boot(bytes(4096))
    def test_header_cannot_claim_missing_payload(self):
        blob=bytearray(4096);blob[:8]=b'ANDROID!'
        struct.pack_into('<4I',blob,8,1024,0,0,1584)
        struct.pack_into('<I',blob,40,4)
        with self.assertRaisesRegex(ValueError,'length'):
            verify.inspect_boot(blob)
    def test_recovery_v2_is_not_a_v4_image(self):
        blob=bytearray(4096);blob[:8]=b'ANDROID!'
        struct.pack_into('<4I',blob,8,0,0,0,1584)
        struct.pack_into('<I',blob,40,2)
        with self.assertRaisesRegex(ValueError,'v4'):
            verify.inspect_boot(blob)
if __name__=='__main__':
    unittest.main()
