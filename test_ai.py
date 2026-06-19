import sys, traceback
sys.path.append('app')
from ai_engine import _call_llm

try:
    print(_call_llm([{'role':'user','content':'hello'}], max_tokens=100))
except Exception as e:
    traceback.print_exc()
