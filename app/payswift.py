import httpx

class PaySwift:
    def __init__(self, base_url: str, client=None): self.base_url=base_url.rstrip('/'); self.client=client or httpx.Client(timeout=3)
    def payouts(self, rider_id):
        r=self.client.get(f'{self.base_url}/v1/payouts',params={'rider_id':rider_id}); r.raise_for_status(); return r.json()
    def pay(self, rider_id, amount, reference, key):
        r=self.client.post(f'{self.base_url}/v1/payouts',json={'rider_id':rider_id,'amount':amount,'reference':reference},headers={'Idempotency-Key':key}); r.raise_for_status(); return r.json()
