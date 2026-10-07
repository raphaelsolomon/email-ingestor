# Correction Flow Testing Guide

## Files Ready for Testing

Two test emails are ready in `emails/`:
- `CORRECTION_TEST_1.eml` 
- `CORRECTION_TEST_2.eml`

✅ **These are .eml files - no modifications needed!**

---

## Scenario 1: CORRECTION_TEST_1.eml
**Expected to be misclassified as P2 (should be P3)**

Content: Urgent tone ("URGENT!!!") but no actual deadline. Just a casual follow-up.

### Test Workflow:
1. **Ingest:** Run "Ingest uploaded files" → emails loaded
2. **Judge:** Run "Run Judge now" 
3. **Verify:** Click the thread "URGENT - URGENT - URGENT"
   - Should show: **Priority P2** (incorrectly classified)
4. **Correct:** Click "Correct this judgement"
   - Select: **"Wrongly Classified"**
   - Enter reason: `No actual deadline - just urgent tone on casual follow-up request`
5. **Re-judge:** Run "Run Judge now" again
6. **Verify learning:** Judge should now recognize "urgent tone without deadline" = P3

---

## Scenario 2: CORRECTION_TEST_2.eml
**Expected to be misclassified as P3 (should be P2)**

Content: Casual tone but contains "need confirmation by end of today" - same-day deadline buried in friendly language.

### Test Workflow:
1. **Ingest:** Run "Ingest uploaded files"
2. **Judge:** Run "Run Judge now"
3. **Verify:** Click the thread "Just a thought"
   - Should show: **Priority P3** (incorrectly classified)
4. **Correct:** Click "Correct this judgement"
   - Select: **"Wrongly Classified"**
   - Enter reason: `Contains same-day deadline (EOD) for supplier confirmation - casual tone shouldn't override deadline`
5. **Re-judge:** Run "Run Judge now" again
6. **Verify learning:** Judge should now catch buried deadlines in casual emails

---

## Testing the Feedback Loop

After corrections, the Judge learns:

- **Scenario 1 learning:** Urgent language without explicit deadline = P3
- **Scenario 2 learning:** Same-day deadline even in casual tone = P2

Next judge runs will include these corrections in the prompt (`past_corrections` array).

---

## Database Inspection (Optional)

Check stored corrections:
```sql
SELECT * FROM correction;
SELECT * FROM judgement WHERE thread_id IN (SELECT DISTINCT thread_id FROM correction);
```

---

## Expected Behavior

✅ Initial judgement: Emails misclassified
✅ User corrects: Provides semantic reason  
✅ Judge re-runs: Should adjust similar emails
✅ Learning verified: Correction impacts future classifications

**That's the full P3 feedback loop working!**
