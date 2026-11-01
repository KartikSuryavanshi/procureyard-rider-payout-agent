from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from .agent import Agent
from .config import settings
from .payswift import PaySwift
from .store import Store

app=FastAPI(title='QuickDrop Rider Payout Dispute Desk')
store=Store(settings.data_dir,settings.db_path); agent=Agent(store,PaySwift(settings.payswift_base_url),settings)
class Message(BaseModel):
    message_id: str = Field(min_length=1,max_length=200)
    rider_id: str = Field(pattern=r'^R\d{3}$')
    text: str = Field(min_length=1,max_length=4000)
    received_at: str
@app.get('/health')
def health(): return {'status':'ok'}
@app.post('/messages')
def messages(msg: Message):
    dup=store.duplicate(msg.message_id)
    if dup: return {'reply':dup['reply']}
    if msg.rider_id not in store.riders_by_id: raise HTTPException(404,'Unknown rider')
    return agent.handle(msg.model_dump())
@app.get('/trace/{rider_id}')
def trace(rider_id: str): return store.get_trace(store.normalize_rider(rider_id))
@app.get('/ops/pending')
def pending(): return store.pending()
@app.get('/ops', response_class=HTMLResponse)
def ops_page():
    items=store.pending()
    rows=''.join(f"<tr><td>{x['id']}</td><td>{x['rider_id']}</td><td>{x['type']}</td><td>{x['amount'] or ''}</td><td>{x['reason']}</td><td><button onclick=decide('{x['id']}','approved')>Approve</button> <button onclick=decide('{x['id']}','rejected')>Reject</button></td></tr>" for x in items)
    return f'''<!doctype html><meta charset="utf-8"><title>QuickDrop Ops Desk</title><h1>Pending rider payout work</h1><table border="1" cellpadding="6"><tr><th>ID</th><th>Rider</th><th>Type</th><th>Amount</th><th>Reason</th><th>Decision</th></tr>{rows}</table><script>async function decide(id,d){{await fetch('/ops/pending/'+id,{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{decision:d}})}});location.reload()}}</script>'''
@app.post('/ops/pending/{item_id}')
def decide(item_id: str, payload: dict):
    if not store.decide_pending(item_id,payload.get('decision','')): raise HTTPException(404,'Pending item not found or invalid decision')
    return {'status':payload['decision'],'id':item_id}
