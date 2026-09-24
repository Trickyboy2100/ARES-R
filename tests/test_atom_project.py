import json,unittest
from ares_r.adapters.atom_project import decode_response


class AtomProjectTest(unittest.TestCase):
    def test_decode_length_prefixed_json(self):
        body=json.dumps({"status":0,"message":[{"graphName":"物料放置最右点"}]},
                        ensure_ascii=False).encode()
        self.assertEqual(decode_response(len(body).to_bytes(8,"little")+body)[0]["graphName"],
                         "物料放置最右点")

    def test_truncated_response_fails(self):
        with self.assertRaises(ValueError):decode_response((10).to_bytes(8,"little")+b"{}")


if __name__=="__main__":unittest.main()
