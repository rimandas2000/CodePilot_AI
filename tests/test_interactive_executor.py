from pathlib import Path
import shutil, sys, tempfile, time, unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))
from executor import InteractiveRun, prepare_commands, run_code

def wait_for(check, timeout=10):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if check(): return
        time.sleep(.02)
    raise AssertionError('Program did not reach expected state')

class ConsoleTests(unittest.TestCase):
    def job(self, language, source, **kwargs):
        job=InteractiveRun(language, source, **kwargs); self.addCleanup(job.stop); return job
    def test_python_live_multiple_inputs(self):
        job=self.job('Python','a=int(input("First: "));b=int(input("Second: "));print("SUM",a+b)')
        wait_for(lambda:'First:' in job.snapshot()['stdout']); self.assertFalse(job.done.is_set())
        job.send_input('10');wait_for(lambda:'Second:' in job.snapshot()['stdout']);job.send_input('20')
        self.assertTrue(job.done.wait(5));self.assertIn('SUM 30',job.snapshot()['stdout']);self.assertTrue(job.snapshot()['success'])
        self.assertFalse(Path(job.work_directory).exists())
    def test_eof(self):
        job=self.job('Python','import sys;print("Reading");print("TOTAL",sum(int(x) for x in sys.stdin))')
        wait_for(lambda:'Reading' in job.snapshot()['stdout']);job.send_input('3');job.send_input('4');job.close_input()
        self.assertTrue(job.done.wait(5));self.assertIn('TOTAL 7',job.snapshot()['stdout'])
        with self.assertRaises(ValueError):job.send_input('5')
    def test_stop_cleanup(self):
        job=self.job('Python','import time;print("Started");time.sleep(60)')
        wait_for(lambda:'Started' in job.snapshot()['stdout']);job.stop();self.assertTrue(job.done.wait(5))
        self.assertEqual(job.snapshot()['status'],'Stopped');self.assertFalse(Path(job.work_directory).exists())
    def test_runtime_limit(self):
        job=self.job('Python','while True: pass',max_runtime=.2);self.assertTrue(job.done.wait(5))
        self.assertEqual(job.snapshot()['status'],'Execution time limit reached')
    def test_output_limit(self):
        job=self.job('Python','while True: print("x"*2000)',max_output=4096);self.assertTrue(job.done.wait(5))
        self.assertEqual(job.snapshot()['status'],'Output limit reached');self.assertLessEqual(len(job.snapshot()['stdout']),4096)
    def test_invalid_source(self):
        result=run_code('Python','if :');self.assertFalse(result['success']);self.assertIn('SyntaxError',result['stdout'])
    def test_missing_runtime_and_empty_code(self):
        with patch('executor._find_command',return_value=None):result=run_code('C','int main(){return 0;}')
        self.assertIn('Install GCC',result['stdout']);self.assertFalse(run_code('Python','')['success']);self.assertFalse(run_code('Rust','x')['success'])
    def test_current_python(self):
        with tempfile.TemporaryDirectory() as folder:_,command=prepare_commands('Python','print(1)',folder)
        self.assertEqual(command[0],sys.executable);self.assertIn('-u',command)
    @unittest.skipUnless(shutil.which('gcc'),'GCC missing')
    def test_c_live_prompt(self):
        job=self.job('C','#include <stdio.h>\nint main(){int n;printf("Number: ");scanf("%d",&n);printf("DOUBLE %d\\n",n*2);}')
        wait_for(lambda:job.snapshot()['accepts_input'] and job.snapshot()['stdout'].endswith('Number: '));job.send_input('21');self.assertTrue(job.done.wait(5));self.assertIn('DOUBLE 42',job.snapshot()['stdout'])
    @unittest.skipUnless(shutil.which('g++'),'G++ missing')
    def test_cpp_live_prompt(self):
        job=self.job('C++','#include <iostream>\nint main(){int n;std::cout<<"Number: ";std::cin>>n;std::cout<<"DOUBLE "<<n*2;}')
        wait_for(lambda:job.snapshot()['accepts_input'] and job.snapshot()['stdout'].endswith('Number: '));job.send_input('21');self.assertTrue(job.done.wait(5));self.assertIn('DOUBLE 42',job.snapshot()['stdout'])
    @unittest.skipUnless(shutil.which('node'),'Node missing')
    def test_javascript_live_input(self):
        job=self.job('JavaScript','const rl=require("readline").createInterface({input:process.stdin,output:process.stdout});rl.question("Name: ",n=>{console.log("HELLO",n);rl.close()});')
        wait_for(lambda:'Name:' in job.snapshot()['stdout']);job.send_input('Debapratim');wait_for(lambda:'HELLO Debapratim' in job.snapshot()['stdout']);job.close_input();self.assertTrue(job.done.wait(5));self.assertIn('HELLO Debapratim',job.snapshot()['stdout'])
    def test_java_constructor_package_preserved(self):
        source='package demo; public class Greeting {public Greeting(){} public static void main(String[] args){new Greeting();}}'
        with tempfile.TemporaryDirectory() as folder,patch('executor._find_command',side_effect=lambda n:n):
            compile_command,command=prepare_commands('Java',source,folder)
            self.assertEqual((Path(folder)/'Greeting.java').read_text(),source);self.assertIn('demo.Greeting',command);self.assertIn('-d',compile_command)
    @unittest.skipUnless(shutil.which('java') and shutil.which('javac'),'JDK missing')
    def test_java_live_input(self):
        job=self.job('Java','import java.util.Scanner; public class Greeting {public Greeting(){} public static void main(String[] a){new Greeting();System.out.print("Number: ");int n=new Scanner(System.in).nextInt();System.out.println("DOUBLE "+n*2);}}')
        wait_for(lambda:'Number:' in job.snapshot()['stdout'],20);job.send_input('21');self.assertTrue(job.done.wait(5));self.assertIn('DOUBLE 42',job.snapshot()['stdout'])
