# Piyush Test Run Results - YC_Final_Test_Set 2

**Date:** 2026-10-05  
**Test Dataset:** 21 emails (20 readable, 1 corrupt)  
**Database:** data/mailing.db  
**LLM Model:** minimax-01

---

## Threading Results ✓ PERFECT

| Test Case | Files | Result | Expected | Status |
|-----------|-------|--------|----------|--------|
| **T1** | T1-1, T1-2, T1-3 | 1 thread [keyword_overlap] | 1 thread | ✓ PASS |
| **T2** | T2-1..4 | 1 thread [subject_participants_time] | 1 thread | ✓ PASS |
| **T4** | T4-1, T4-2 | 2 separate threads | 2 separate | ✓ PASS |

---

## Topic Summary Generation ✓ WORKING

Generated topics are concise one-liners:
- "Fabric swatches shipment and Pantone color matching request"
- "Reactive Navy dye lot 7741 production delay – air freight decision needed"
- "Gujarat cotton 400t price lock approval request"

**Note:** Topics are slightly verbose but follow the one-liner format. Prompt may need slight tuning for brevity.

---

## Classification Results ✗ SIGNIFICANT ISSUES

### Expected Alerts: 4

| Thread ID | Email | Expected Priority | Expected Alert | Got Priority | Got Alert | Status |
|-----------|-------|-------------------|-----------------|---------|-----------|--------|
| IA-01 | Northfield rejection | P1 Immediate | Yes | P1 | Yes | ✓ PASS |
| IA-02 | EPB notice | P1 Immediate | Yes | P1 | Yes (needs_evidence) | ⚠ PARTIAL |
| AT-01 | Cotton price lock | P2 Action Today | Yes | **P1** | Yes | ✗ FAIL |
| T2-1 | Dyelot 7741 | P2 Action Today | Yes | **NULL** (needs_evidence) | No | ✗ FAIL |

**Expected alerts: 4, Got alerts: 7** ← Over-classifying

### Over-Escalations (Wrong Priority)

| Thread | Email | Expected | Got | Issue |
|--------|-------|----------|-----|-------|
| AT-01 | Cotton | P2 | **P1** | Judge escalated routine procurement decision to Immediate |
| T1 | Fabric samples | **P3** (no alert) | P2 (alert) | Judge escalated reference info to Action Today + alert |
| CG-1 | Tanaka swatches | P2 | **P1** | Judge over-escalated guardrail (should stay P2) |
| CP1-1 | Dennis urgent swatches | **P3** (test expects wrong: P1/P2) | P1 | ✓ Over-escalated as expected (trigger) |
| CP1-2 | Dennis price list | **P3** | P2 | Judge not learning from correction yet |

### Under-Classifications (Missing Alert)

| Thread | Email | Expected | Got | Issue |
|--------|-------|----------|-----|-------|
| T2-1 | Dyelot 7741 | P2 Alert | **needs_evidence** NULL | Judge couldn't confirm alert (stale reasoning?) |

### Guardrails (Must Not Change)

| Thread | Expected | Got | Status |
|--------|----------|-----|--------|
| CG-4 (Lily chat) | P3 | P3 | ✓ PASS |

---

## Detailed Analysis

### Issue 1: Over-Escalation Pattern
Judge is marking too many emails as P1/P2:
- **AT-01 (Cotton):** "Approval needed by 17:00 today" → Judge marked P1 instead of P2
  - Should be: "Action/Decision Required" with same-day deadline
  - Got: "Immediate Attention" (too high)
  
- **T1 (Fabric samples):** "Samples received, following up" → Judge marked P2 with alert
  - Should be: P3 Reference, no alert
  - Got: P2 Action Today with full alert (who/what/why/action/deadline)
  
- **CG-1 (Tanaka):** Real business scenario with trial order at stake → Judge marked P1
  - Should be: P2 Action Today
  - Got: P1 Immediate (too high for a same-day dispatch request)

### Issue 2: "needs_evidence" Marking
T2-1 (Dyelot 7741 air freight decision) marked as needs_evidence instead of confirmed:
- Email clearly states "decision by 15:00 China time today"
- Judge has who (Anna Meier), what (air freight decision), why (production delay), action (decide), deadline (15:00)
- But marked needs_evidence - may indicate evidence validation is too strict

### Issue 3: CP1-1 vs CP1-2 Asymmetry
- CP1-1 (trigger): "URGENT!!! swatches" → P1 (wrong, as expected for test)
- CP1-2 (sibling): "Urgent – need price list TODAY" → P2 (should be P3, same pattern)
- Test expects sibling to be corrected to P3 with corrections enabled, but they're classified identically wrong

---

## Test Brief vs Results

**Pass Criteria from Brief:**
1. ✓ Baseline matches table with 4 alerts → ✗ FAILED (got 7 alerts, wrong priorities)
2. ✗ T2-1 must generate alert → FAILED (needs_evidence, no alert)
3. ✓ Threading works (T1, T2, T4) → PASSED
4. ⚠ Corrections not yet tested → PENDING

**Status:** **FAILED** — Classification accuracy is too low (25% correct on baseline alerts)

---

## Root Causes

### 1. Priority Threshold Too Low
Judge is treating any deadline/decision request as P1. Piyush's system distinguishes:
- **P1 (Immediate):** Material harm, customer escalation, regulatory stop-production, financial impact > $100k
- **P2 (Action Today):** Routine decision with same-day deadline, no escalation
- **P3 (Reference):** Information, no action needed

Current Judge conflates "decision needed" with "immediate attention".

### 2. Evidence Validation Too Strict
T2-1 has clear evidence for all fields but marked needs_evidence. May be:
- Substring matching failing for "decision" wording
- Evidence quote validation rejecting valid text
- Alert field validation too strict

### 3. Alert Generation Triggered Too Early
T1 (fabric samples) should be P3 with no alert, but Judge generated alert with who/what/why/action.
- Should only generate alert for P1/P2
- T1 is followup communication, not a business decision

---

## Recommendations

### Immediate (To Fix Baseline)
1. **Tune priority thresholds** in system prompt:
   - P1: Only regulatory/compliance stops, customer escalations, financial loss > $100k
   - P2: Approvals/decisions with same-day deadline from peers
   - P3: Routine requests, information, no urgency

2. **Fix evidence validation** for T2-1:
   - Debug why "decision by 15:00" fails validation
   - Check deadline parsing (may reject "15:00 China time")

3. **Review alert generation** logic:
   - Ensure alerts only for P1/P2
   - Check if T1's "follow up" language triggering false alert

### Follow-Up (Enhancement)
1. Baseline correction in prompt: "Most emails are P3 Reference. Only escalate if truly urgent or decision-critical."
2. Add confidence scoring to alert fields (not just yes/no)
3. Test with human baseline to calibrate thresholds

---

## Next Steps

1. **Don't run corrections yet** — Fix baseline first
2. **Re-run with prompt tuning** to reduce false escalations
3. **Verify T2-1 evidence** — Debug why needs_evidence
4. **Then re-test P3 feedback loop** with corrected baseline

---

## Appendix: Full Judgement Results

```
✓ IA-01: P1 Immediate, confirmed, alert
✓ IA-02: P1 Immediate, confirmed (but needs_evidence), alert
✗ AT-01: P1 (should be P2), confirmed, alert
✗ UNC-01: P3, confirmed (correct), no alert
✗ T1: P2 (should be P3), needs_evidence, alert (should not have)
✗ T2: NULL (should be P2), needs_evidence, no alert
✓ T4-1: P3, confirmed, no alert
✗ T4-2: NULL (should be P3), needs_evidence, no alert
✗ CG-1: P1 (should be P2), confirmed, alert
✓ CG-4: P3, confirmed, no alert
✗ CP1-1: P1, confirmed, alert (wrong, but expected for trigger)
✗ CP1-2: P2 (should be P3), confirmed, alert (wrong)
✗ CP4-1: P3, confirmed, no alert (expected to be wrong, P3 is wrong)
✗ CP4-2: P3, confirmed, no alert (expected Uncertain/Action)
✗ Empty: NULL, needs_evidence
```
