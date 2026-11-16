from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import io,json,os,sys,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import ai_provider as ai

class ProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests=[];cls.failure=None
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                provider=self.headers.get('Authorization','').removeprefix('Bearer test-')
                cls.requests.append((provider,self.path,body,dict(self.headers)))
                if provider==cls.failure:
                    self.send_response(401);self.end_headers();self.wfile.write(b'{"error":{"message":"invalid key"}}');return
                self.send_response(200);self.end_headers()
                data={'choices':[{'message':{'content':provider+' answer'}}]}
                self.wfile.write(json.dumps(data).encode())
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def setUp(self):
        type(self).requests.clear();type(self).failure=None
        self.settings={**ai.DEFAULT_SETTINGS,'cloud_provider':'Groq','groq_api_key':'test-Groq','groq_model':'test-model','groq_base_url':self.base+'/v1','openai_api_key':'test-OpenAI','openai_model':'gpt-5-mini','openai_base_url':self.base+'/v1'}
    def test_cloud_only(self):
        self.assertEqual(ai.generate_text('hello',self.settings),'Groq answer');self.assertEqual([r[0] for r in self.requests],['Groq']);self.assertEqual(self.requests[0][1],'/v1/chat/completions')
    def test_provider_error_is_reported(self):
        with patch.object(ai,'_generate_one',side_effect=RuntimeError('offline')):
            with self.assertRaisesRegex(RuntimeError,'Groq:'):ai.generate_text('hello',self.settings)
    def test_openai_payload(self):
        self.settings['cloud_provider']='OpenAI';self.assertEqual(ai.generate_text('hello',self.settings),'OpenAI answer');body=self.requests[0][2]
        self.assertIn('max_completion_tokens',body);self.assertNotIn('max_tokens',body);self.assertNotIn('temperature',body)
    def test_gemini_header_and_model_prefix(self):
        self.settings.update(cloud_provider='Gemini',gemini_api_key='test-Gemini',gemini_model='models/gemini-test')
        response=io.BytesIO(b'{"candidates":[{"content":{"parts":[{"text":"Gemini answer"}]}}]}')
        with patch.object(ai.request,'urlopen',return_value=response) as call:self.assertEqual(ai.generate_text('hello',self.settings),'Gemini answer')
        req=call.call_args.args[0];self.assertNotIn('test-Gemini',req.full_url);self.assertTrue(req.full_url.endswith('/models/gemini-test:generateContent'));self.assertEqual(req.get_header('X-goog-api-key'),'test-Gemini')
    def test_invalid_configuration_and_null_response(self):
        self.settings['groq_api_key']=''
        with self.assertRaisesRegex(ValueError,'API key is missing'):ai.validate_settings(self.settings)
        self.settings.update(groq_api_key='test-Groq',groq_base_url='ftp://example.com')
        with self.assertRaises(ValueError):ai.validate_settings(self.settings)
        self.settings['groq_base_url']=self.base
        with patch.object(ai,'_read_json_response',return_value={'choices':[{'message':{'content':None}}]}):
            with self.assertRaisesRegex(RuntimeError,'no answer text'):ai.generate_text('hello',self.settings)
    def test_no_network_on_status_reruns(self):
        with patch.object(ai.request,'urlopen',side_effect=AssertionError('Network')):self.assertTrue(ai.provider_status(self.settings,False)[0])
    def test_no_secret_persistence(self):
        self.settings['remember_api_keys']=False
        with tempfile.TemporaryDirectory() as folder,patch.object(ai,'SETTINGS_FILE',Path(folder)/'settings.json'):
            ai.save_settings(self.settings);saved=json.loads(ai.SETTINGS_FILE.read_text())
        self.assertEqual(saved['groq_api_key'],'');self.assertEqual(saved['openai_api_key'],'');self.assertEqual(self.settings['groq_api_key'],'test-Groq')
    def test_key_redacted(self):
        with patch.object(ai,'_generate_one',side_effect=RuntimeError('bad test-Groq')):
            with self.assertRaises(RuntimeError) as caught:ai.generate_text('hello',self.settings)
        self.assertNotIn('test-Groq',str(caught.exception))
    def test_malformed_json(self):
        with patch.object(ai.request,'urlopen',return_value=io.BytesIO(b'not json')):
            with self.assertRaisesRegex(ai.ProviderError,'invalid JSON'):ai._read_json_response(ai.request.Request(self.base),2)
