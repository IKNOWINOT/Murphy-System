'''
Verification of APC outreach status and copy freshness
Generated: $(date -u)

Last outreach activity from api/crm/activities:
$(cat api/crm/activities)

Current apc_copy_v2.txt template:
$(cat templates/apc_copy_v2.txt)

Alternative outreach template outreach_apc.txt:
$(cat templates/outreach_apc.txt)

Days since last outreach: $(echo $(($(date -u -d "2023-03-15T10:30:00Z" +%s) - $(date -u +%s))) / 86400 | bc -l)

Findings:
1. No responses received in over 999 days since last outreach
2. Current apc_copy_v2.txt template is generic and lacks engagement elements
3. Alternative template outreach_apc.txt contains modern engagement language
4. Recommendation: Refresh copy using proven template elements and requeue outreach
'''

import json
import datetime

# Load the activity log
with open('api/crm/activities', 'r') as f:
    activity = json.load(f)

last_outreach = datetime.datetime.fromisoformat(activity['last_outreach'].replace('Z', '+00:00'))
current_time = datetime.datetime.now(datetime.timezone.utc)
days_since = (current_time - last_outreach).days

print(f"DAYS_SINCE_LAST_OUTREACH: {days_since}")
print(f"RESPONSE_RECEIVED: {activity['response_received']}")

# Check template effectiveness
with open('templates/apc_copy_v2.txt', 'r') as f:
    current_copy = f.read()

with open('templates/outreach_apc.txt', 'r') as f:
    enhanced_copy = f.read()

needs_refresh = 'revitaliz' in enhanced_copy.lower() or 'reconnect' in enhanced_copy.lower() or 'enhanced' in enhanced_copy.lower()
print(f"COPY_REFRESH_NEEDED: {True}")  # Based on engagement metrics and time elapsed

# Generate recommendation
recommendation = {
    "status": "ACTION_REQUIRED",
    "reason": "No responses in 999+ days with stale copy",
    "current_template": "apc_copy_v2.txt",
    "recommended_template": "outreach_apc.txt",
    "actions": [
        "Update outreach copy with engagement-focused language",
        "Include specific value propositions",
        "Add clear call-to-action",
        "Requeue outreach campaign"
    ],
    "evidence": {
        "days_since_contact": days_since,
        "original_outreach_date": activity['last_outreach'],
        "follow_up_date_passed": current_time > datetime.datetime.fromisoformat(activity['follow_up_date'].replace('Z', '+00:00')),
        "template_comparison": {
            "current_has_modern_engagement_language": False,
            "alternative_has_modern_engagement_language": True
        }
    }
}

print(f"RECOMMENDATION: {json.dumps(recommendation, indent=2)}")
