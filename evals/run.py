import json,sys,time,httpx
from pathlib import Path
def main(base):
    cases=json.loads((Path(__file__).parents[1]/'data/conversations.json').read_text()); client=httpx.Client(base_url=base,timeout=10); passed=0
    for case in cases:
        for turn in case['turns']:
            if turn['from']=='rider': client.post('/messages',json={'message_id':turn['message_id'],'rider_id':case['rider_id'],'text':turn['text'],'received_at':turn['received_at']})
        pending=client.get('/ops/pending').json(); trace=client.get('/trace/'+case['rider_id']).json(); expected=case['expected']; text=' '.join(str(x.get('output','')) for x in trace)
        ok=all(str(x) in text for x in expected.get('reply_mentions',[])) if expected.get('reply_mentions') else True
        print(('PASS' if ok else 'FAIL'),case['scenario'],'trace_steps=',len(trace),'pending=',len(pending)); passed += ok
    print(f'{passed}/{len(cases)} cases passed (conversation/content smoke evaluation)')
if __name__=='__main__': main(sys.argv[1])
