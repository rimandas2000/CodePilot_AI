"""Real Streamlit page/form workflows with isolated local data and fake AI."""
import json,os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import ai_provider as ai
ROOT=Path(__file__).resolve().parents[1]

class AppTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.env=patch.dict(os.environ,{'CODEPILOT_DATA_DIR':self.folder.name});self.env.start();self.addCleanup(self.env.stop)
        self.settings_path=Path(self.folder.name)/'settings.json'
        self.store=patch.object(ai,'SETTINGS_FILE',self.settings_path);self.store.start();self.addCleanup(self.store.stop)
        self.app=AppTest.from_file(str(ROOT/'backend'/'app.py'),default_timeout=20).run()
        self.app.session_state['authenticated']=True;self.app.session_state['user_name']='Test User'
        self.app.run();self.assertNoExceptions()
    def tearDown(self):
        try:
            job=self.app.session_state['compiler_job']
            if job:job.stop();job.done.wait(6)
        except KeyError:pass
    def assertNoExceptions(self):
        self.assertFalse(self.app.exception,[e.message for e in self.app.exception])
    def page(self,name):
        self.app.session_state['page']=name;self.app.run();self.assertNoExceptions()
    def test_all_navigation_pages(self):
        for name in ['Home','Chat (AI Mentor)','Compiler / Run Code','Debug & Fix','Explain Code','Improve Code','Convert Code','Dashboard','Recent Activity','Settings','About']:
            with self.subTest(page=name):self.page(name)
    def test_console_input_and_removed_sections(self):
        self.app.session_state['code_compiler']='x=input("Number: ");print("VALUE",x)'
        self.page('Compiler / Run Code')
        text='\n'.join(m.value for m in self.app.markdown)
        self.assertNotIn('Standard Input (optional)',text);self.assertNotIn('Timeout (seconds)',text)
        self.app.button(key='run_compile').click().run()
        deadline=time.monotonic()+5
        while time.monotonic()<deadline and not self.app.session_state['compiler_job'].snapshot()['accepts_input']:time.sleep(.02)
        self.app.run();self.assertNoExceptions()
        self.app.text_input(key='console_input_line').set_value('1729')
        self.app.button(key='FormSubmitter:console_input_form-Send Input ↵').click().run()
        self.assertTrue(self.app.session_state['compiler_job'].done.wait(5));self.app.run();self.assertNoExceptions()
        self.assertIn('VALUE 1729','\n'.join(v.value for v in self.app.code))
        self.assertEqual(self.app.session_state['usage']['successful_runs'],1)
        self.app.run();self.assertEqual(self.app.session_state['usage']['successful_runs'],1)
    def test_session_only_cloud_key_survives_save_and_request(self):
        self.page('Settings');self.app.toggle(key='setting_ollama_enabled').set_value(False)
        self.app.toggle(key='setting_cloud_enabled').set_value(True).run()
        self.app.selectbox(key='setting_provider').set_value('Groq').run()
        self.app.text_input(key='setting_groq_key').set_value('test-Groq')
        self.app.checkbox(key='setting_remember_keys').set_value(False)
        self.app.button(key='save_settings').click().run();self.assertNoExceptions()
        self.assertEqual(self.app.session_state['settings']['groq_api_key'],'test-Groq')
        self.assertEqual(json.loads(self.settings_path.read_text())['groq_api_key'],'')
        self.page('Home');revision=self.app.session_state['home_question_rev']
        self.app.text_area(key=f'home_question_{revision}').set_value('Hello')
        with patch.object(ai,'_generate_one',return_value='Cloud works') as call:self.app.button(key='ask_home').click().run()
        self.assertNoExceptions();self.assertEqual(call.call_args.args[0],'Groq')
        self.assertEqual(self.app.session_state['home_messages'][-1]['content'],'Cloud works')
    def test_both_settings_and_both_answers(self):
        self.page('Settings');self.app.toggle(key='setting_cloud_enabled').set_value(True).run()
        self.app.selectbox(key='setting_provider').set_value('Groq').run()
        self.app.text_input(key='setting_groq_key').set_value('test-Groq');self.app.button(key='save_settings').click().run()
        self.assertEqual(ai.enabled_providers(self.app.session_state['settings']),['Ollama','Groq'])
        self.page('Home');revision=self.app.session_state['home_question_rev'];self.app.text_area(key=f'home_question_{revision}').set_value('Hello')
        with patch.object(ai,'_generate_one',side_effect=lambda name,*a:name+' response'):self.app.button(key='ask_home').click().run()
        answer=self.app.session_state['home_messages'][-1]['content'];self.assertIn('Ollama response',answer);self.assertIn('Groq response',answer);self.assertNoExceptions()
    def test_invalid_settings_do_not_replace_active_mode(self):
        self.page('Settings');self.app.toggle(key='setting_ollama_enabled').set_value(False).run();self.app.button(key='save_settings').click().run()
        self.assertTrue(self.app.error);self.assertEqual(ai.enabled_providers(self.app.session_state['settings']),['Ollama']);self.assertFalse(self.settings_path.exists())
    def test_usage_write_error_does_not_break_chat(self):
        revision=self.app.session_state['home_question_rev'];self.app.text_area(key=f'home_question_{revision}').set_value('Hello')
        with patch('json_storage.atomic_write_json',side_effect=PermissionError('locked')),patch.object(ai,'_generate_one',return_value='Retained answer'):
            self.app.button(key='ask_home').click().run()
        self.assertNoExceptions();self.assertEqual(self.app.session_state['home_messages'][-1]['content'],'Retained answer')
    def test_provider_error_remains_visible_after_rerun(self):
        revision=self.app.session_state['home_question_rev'];self.app.text_area(key=f'home_question_{revision}').set_value('Hello')
        with patch.object(ai,'_generate_one',side_effect=RuntimeError('Provider unavailable')):self.app.button(key='ask_home').click().run()
        self.assertNoExceptions();self.assertTrue(self.app.error);self.assertIn('Provider unavailable',self.app.error[0].value)
    def test_sign_out_clears_previous_session_data(self):
        self.app.session_state['home_messages']=[{'role':'assistant','content':'private'}]
        self.app.button(key='sign_out').click().run();self.assertNoExceptions();self.assertFalse(self.app.session_state['authenticated']);self.assertEqual(self.app.session_state['home_messages'],[])
    def test_malformed_usage_file_still_opens_dashboard(self):
        (Path(self.folder.name)/'usage.json').write_text(json.dumps({'lines_processed':'bad','total_active_seconds':None,'activity':['bad',{'label':123}]}))
        del self.app.session_state['usage'];self.app.session_state['page']='Dashboard';self.app.run();self.assertNoExceptions()
        self.assertIsInstance(self.app.session_state['usage']['lines_processed'],int)

    def test_create_account_and_sign_in(self):
        self.app.session_state['authenticated']=False;self.app.session_state['auth_mode']='signup';self.app.run()
        self.app.text_input[0].set_value('Tester')
        self.app.text_input(key='signup_email').set_value('tester@example.com')
        self.app.text_input(key='signup_password').set_value('test-password')
        self.app.text_input[3].set_value('test-password')
        self.app.button(key='FormSubmitter:signup_form-Create account  →').click().run();self.assertNoExceptions()
        users=json.loads((Path(self.folder.name)/'users.json').read_text());self.assertTrue(users['tester@example.com']['password_hash'].startswith('pbkdf2_sha256$'))
        self.app.session_state['auth_mode']='signin';self.app.run()
        self.app.text_input[0].set_value('tester@example.com');self.app.text_input[1].set_value('test-password')
        self.app.button(key='FormSubmitter:signin_form-↪  Sign In  →').click().run();self.assertNoExceptions();self.assertTrue(self.app.session_state['authenticated'])
    def test_settings_save_permission_failure_is_visible(self):
        self.page('Settings')
        with patch.object(ai,'atomic_write_json',side_effect=PermissionError('locked')):self.app.button(key='save_settings').click().run()
        self.assertNoExceptions();self.assertTrue(self.app.error);self.assertFalse(self.settings_path.exists())
    def test_corrupt_accounts_cannot_be_overwritten(self):
        users=Path(self.folder.name)/'users.json';users.write_text('broken')
        self.app.session_state['authenticated']=False;self.app.session_state['auth_mode']='signup';self.app.run()
        self.app.text_input[0].set_value('Tester');self.app.text_input(key='signup_email').set_value('tester@example.com')
        self.app.text_input(key='signup_password').set_value('test-password');self.app.text_input[3].set_value('test-password')
        self.app.button(key='FormSubmitter:signup_form-Create account  →').click().run();self.assertNoExceptions();self.assertEqual(users.read_text(),'broken');self.assertTrue(self.app.error)
