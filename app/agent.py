import hashlib, re
from datetime import datetime, timezone
from .calculator import investigate
from .models import PendingItem
from .parser import foreign_rider_claim, parse_complaint

class Agent:
    def __init__(self, store, payswift, settings): self.store=store; self.payswift=payswift; self.settings=settings
    def handle(self, message):
        rid=self.store.normalize_rider(message['rider_id']); text=message['text']; mid=message['message_id']
        duplicate=self.store.duplicate(mid)
        if duplicate: return {'reply':duplicate['reply']}
        self.store.trace(rid,'message_in','rider_message',message,None)
        if foreign_rider_claim(text,rid): reply='Main sirf is number se jude account ke baare mein madad kar sakta hoon. Aapke account ki specific problem bataiye.'; return self.finish(mid,rid,reply)
        parsed=parse_complaint(text)
        prior=self.store.prior_messages(rid)[:-1]
        # Short follow-ups inherit the active complaint, but status questions
        # never trigger a second payment.
        status_followup=bool(prior) and not parsed.dates and not parsed.trip_ids and any(x in text.lower() for x in ('kab tak','abhi de do','thik hai','theek hai'))
        if prior and (parsed.dates or parsed.trip_ids) and not parsed.kinds:
            parsed=parse_complaint(prior[-1]+' '+text)
        self.store.trace(rid,'decision','complaint_parsed',{'text_length':len(text)},{'kinds':sorted(parsed.kinds),'dates':parsed.dates,'trip_ids':parsed.trip_ids})
        if parsed.injection: reply='Main sirf aapke verified account ke records aur payout policy ke basis par complaint check kar sakta hoon. Date ya order ID bataiye.'; self.queue_escalation(rid,'Untrusted instruction in rider message'); return self.finish(mid,rid,reply)
        if status_followup:
            reply='Aapki correction process ho chuki hai. Agar koi approval pending hai to ops team approve karne ke baad PaySwift par payment aayega.'
            return self.finish(mid,rid,reply)
        try: result=investigate(self.store,rid,parsed,message['received_at'])
        except Exception:
            self.queue_escalation(rid,'Investigation service failed'); reply='Abhi records check nahi ho pa rahe. Ops team is complaint ko dekhegi.'; return self.finish(mid,rid,reply)
        self.store.trace(rid,'tool_call','investigate_payout',{'rider_id':rid},{'owed':result.owed,'facts':result.facts})
        if result.unresolved:
            reply=result.reason if 'provide' in result.reason else f'{result.reason} Ops team isse review karegi.'
            if 'provide' not in result.reason: self.queue_escalation(rid,result.reason)
            return self.finish(mid,rid,reply)
        amount=result.owed
        if amount<=0:
            reply='Records ke hisaab se is complaint mein koi confirmed shortfall nahi mila. ' + ' '.join(result.facts[:2])
            if any(x in text.lower() for x in ('dobara','wrong','galat','disagree')): self.queue_escalation(rid,'Rider disputes confirmed records')
            return self.finish(mid,rid,reply)
        today=message['received_at'][:10]
        already=sum(int(x.get('amount',0)) for x in self.payswift.payouts(rid) if x.get('created_at','')[:10]==today)
        # A large batch of missing orders is one high-value correction and
        # must wait in full for ops. Small multi-issue disputes may use the
        # remaining daily allowance and queue only the remainder.
        if amount > self.settings.auto_pay_limit and parsed.kinds == {'missing'}:
            auto = 0
        else:
            auto=min(amount,max(0,self.settings.auto_pay_limit-already))
        approval=amount-auto
        if auto:
            try: self.payswift.pay(rid,auto,f'Payout dispute correction for {rid}',hashlib.sha256(mid.encode()).hexdigest())
            except Exception: self.queue_escalation(rid,'PaySwift payment failed'); return self.finish(mid,rid,'Payment service abhi available nahi hai. Ops team aapki correction dekhegi.')
        if approval: self.queue_approval(rid,approval,'Correction exceeds daily auto-pay limit')
        reply=' '.join(result.facts[:3]) + f' ₹{amount} aapko milne chahiye the.'
        if auto: reply += f' ₹{auto} PaySwift par process ho gaye.'
        if approval: reply += f' ₹{approval} ops approval ke liye bheje gaye hain.'
        return self.finish(mid,rid,reply)
    def finish(self,mid,rid,reply): self.store.trace(rid,'reply','rider_reply',None,reply); self.store.save_message(mid,rid,reply); return {'reply':reply}
    def queue_approval(self,rid,amount,reason): self.store.add_pending(PendingItem('approval-'+hashlib.sha1(f'{rid}{amount}{reason}'.encode()).hexdigest()[:12],rid,'approval',amount,reason,datetime.now(timezone.utc).isoformat()))
    def queue_escalation(self,rid,reason): self.store.add_pending(PendingItem('escalation-'+hashlib.sha1(f'{rid}{reason}'.encode()).hexdigest()[:12],rid,'escalation',None,reason,datetime.now(timezone.utc).isoformat()))
