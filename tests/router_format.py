import asyncio,json,unittest
import httpx
from backend import orchestration as o

class RouterFormat(unittest.TestCase):
    def run_describe(self,handler):
        async def go():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                return await o.describe(client,'http://x/v1','router','fix my python script')
        return asyncio.run(go())
    def test_reply_shape_is_forced(self):
        seen=[]
        def handler(request):
            body=json.loads(request.content); seen.append(body)
            return httpx.Response(200,json={'choices':[{'message':{'content':'{"needs":["coding"],"complexity":"medium","reason":"code fix"}'}}]})
        profile=self.run_describe(handler)
        self.assertEqual(profile['needs'],['coding'])
        schema=seen[0]['response_format']['json_schema']['schema']
        self.assertEqual(schema['properties']['complexity']['enum'],list(o.COMPLEXITY))
        self.assertEqual(set(schema['properties']['needs']['items']['enum']),set(o.NEEDS))
    def test_server_without_structured_output_still_works(self):
        calls=[]
        def handler(request):
            body=json.loads(request.content); calls.append('response_format' in body)
            if 'response_format' in body: return httpx.Response(400,json={'error':'unsupported'})
            return httpx.Response(200,json={'choices':[{'message':{'content':'{"needs":["chat"],"complexity":"low","reason":"hi"}'}}]})
        self.assertEqual(self.run_describe(handler)['complexity'],'low'); self.assertEqual(calls,[True,False])

if __name__=='__main__':unittest.main()
