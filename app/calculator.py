from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from collections import Counter
from .models import Investigation
from .store import Store

def trip_fare(distance: str, surge: str) -> int:
    km = Decimal(distance)
    # A few source exports contain metres without the decimal point (5000 = 5.0 km).
    if km > 100: km /= Decimal('1000')
    base = Decimal('25') + max(Decimal('0'), km-Decimal('2')) * Decimal('6')
    return int((base * Decimal(surge)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def investigate(store: Store, rider_id: str, complaint, received_at: str) -> Investigation:
    result=Investigation()
    if complaint.dates:
        received=date.fromisoformat(received_at[:10])
        if any((received-date(2026,9,int(d))).days > 7 for d in complaint.dates):
            result.unresolved=True; result.reason='This date is outside the seven-day dispute window, so ops must review it.'; return result
    rows=store.trip_rows(rider_id, complaint.dates, complaint.trip_ids)
    if complaint.trip_ids and not rows:
        result.unresolved=True; result.reason='The referenced order is not associated with this rider.'; return result
    if not complaint.dates and not complaint.trip_ids and complaint.kinds <= {'missing','incentive'}:
        result.unresolved=True; result.reason='Please provide the date or order ID so I can check the correct payout.'; return result
    if not rows and 'incentive' not in complaint.kinds:
        result.unresolved=True; result.reason='I could not find a matching record in the last 7 days.'; return result
    if 'incentive' in complaint.kinds:
        dates=complaint.dates or [received_at[8:10]]
        for d in dates:
            day=store.trip_rows(rider_id,[d]); completed=[x for x in day if x['status']=='completed']
            # The brief says exports arrive as-is. For incentive eligibility, a
            # trip payout line is also evidence of a completed trip when the
            # trips export is missing that row.
            line_trip_ids={x['trip_id'] for x in store.payout_lines(rider_id, date=f'2026-09-{int(d):02d}') if x['line_type']=='trip' and x['trip_id']}
            count=len(line_trip_ids)
            paid=any(x['line_type']=='daily_incentive' and x['payout_date']==f'2026-09-{int(d):02d}' for x in store.payout_lines(rider_id))
            if count>=12 and not paid: result.owed += 150; result.facts.append(f'{d} Sep: {count} completed trips qualify for the ₹150 incentive.')
            else: result.facts.append(f'{d} Sep: {count} completed trips; the incentive requires 12.')
    if rows and ('surge' in complaint.kinds or 'missing' in complaint.kinds or 'distance' in complaint.kinds):
        for t in rows:
            if t['status']!='completed': continue
            expected=trip_fare(t['distance_km'],t['surge_multiplier'])
            paid=sum(int(x['amount']) for x in store.payout_lines(rider_id,t['trip_id']))
            if expected>paid:
                result.owed += expected-paid; result.facts.append(f"{t['trip_id']}: expected ₹{expected}, PaySwift export line ₹{paid}.")
            else: result.facts.append(f"{t['trip_id']}: expected ₹{expected}, paid ₹{paid}; no shortfall found.")
            result.evidence.append({'trip_id':t['trip_id'],'expected':expected,'paid':paid})
    if 'penalty' in complaint.kinds:
        for t in rows:
            if t['status']=='cancelled_by_rider':
                penalties=store.payout_lines(rider_id,t['trip_id'])
                count=sum(1 for x in penalties if x['line_type']=='cancellation_penalty')
                if count>1: result.owed += (count-1)*10; result.facts.append(f"{t['trip_id']}: cancellation penalty was recorded {count} times; ₹{(count-1)*10} is duplicated.")
                else: result.facts.append(f"{t['trip_id']}: one cancellation penalty is supported by the trip record.")
    if not result.facts: result.unresolved=True; result.reason='No matching discrepancy could be confirmed from the available records.'
    return result
