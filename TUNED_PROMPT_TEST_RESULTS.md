# Tuned Prompt Test Results

**Date:** 2026-10-05  
**Change:** Updated SYSTEM_PROMPT with explicit P1/P2/P3 guidance and "most emails are P3" baseline  
**Result:** Significant improvement, but two new issues identified

---

## Comparison: Before vs After Tuning

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Correct baseline priorities | 1/4 (25%) | 3/4 (75%) | ✓ +50% |
| Total alerts (expected 4) | 7 | 3 | ✓ Reduced 4 false positives |
| AT-01 (Cotton) | P1 ✗ | P2 ✓ | ✓ FIXED |
| T1 (Samples) | P2 ✗ | P3 ✓ | ✓ FIXED |
| CG-1 (Tanaka) | P1 ✗ | P2 ✓ | ✓ FIXED |
| T2-1 (Dyelot) | NULL ✗ | NULL ✗ | ✗ Still broken |
| CP1-1 (Trigger) | P1 (wrong, as expected) | P3 (correct, breaks demo) | ⚠ Regression |
| CP4-2 (Trigger) | P2 | P4 | ⚠ Regression |

---

## Key Improvement: Priority Tuning Works ✓

New SYSTEM_PROMPT guidance:
```
1 Immediate Attention - ONLY: regulatory/compliance, customer escalations, $100k+ risk
2 Action/Decision Required - routine approvals/decisions with same-day deadline
3 Reference - useful context, status updates
```

Added: "Most emails are P3. Escalate only for genuine crises."

**Result:** Judge now correctly distinguishes:
- ✓ Cotton approval deadline → P2 (not P1)
- ✓ Fabric samples followup → P3 (not P2)
- ✓ Tanaka swatch request → P2 (not P1)

---

## Problem 1: T2-1 Evidence Validation Failure ⚠

**Symptom:** T2-1 (Dyelot air freight decision) marked needs_evidence with NULL priority
- Judge correctly identified: "decision by 15:00 China time today"
- But marked: "priority has no surviving evidence; reason has no surviving evidence"
- Evidence validation rejected ALL quotes (0 surviving)

**Root Cause:** Evidence validation in `judge.py:_validate_evidence()` is too strict
- Quote substring matching may fail on whitespace/encoding differences
- Or message_ref is not matching correctly
- Or source_field extraction is wrong

**Impact:** One baseline alert (T2-1) missing from alerts list

**Fix Needed:** Debug evidence validation or relax substring matching

---

## Problem 2: Correction Test Setup Broken ⚠

**Symptom:** CP1-1 and CP4-2 now classified "correctly"
- CP1-1 (Dennis urgent): Now P3 (correct), but test expects P1 to show it's wrong initially
- CP4-2 (Chen Wei): Now P4 (filtered), but test expects to see wrong classification to correct

**Context:** Correction tests need:
1. Trigger email classified WRONG
2. Then correct it via feedback loop
3. Then sibling should flip to CORRECT

But if Judge is now too conservative, triggers are classified correctly by accident, breaking the demo.

**Impact:** Correction pattern tests won't show learning (trigger already correct = no improvement to demonstrate)

**Example:** CP1-1 "URGENT!!! swatches" → Judge now says P3 (correct!) but test expects P1 (wrong, then correctable)

**Fix Options:**
1. Revert to original prompt for these specific emails only
2. Lower the bar for P1 on "URGENT" + "ASAP" markers (but keeps baseline conservative)
3. Accept that these emails are now classified correctly and adjust test expectations

---

## Summary

**Progress:** 75% baseline correct (up from 25%) ✓
**Remaining Issues:**
1. T2-1 evidence validation failure (0 surviving evidence)
2. Correction triggers now classified correctly (test setup mismatch)

**Baseline Status:**
- IA-01 ✓ P1 with alert
- IA-02 ✓ P1 with alert (marked needs_evidence but has priority)
- AT-01 ✓ P2 with alert
- T2-1 ✗ P1 NULL, no alert (evidence validation failure)

**Next Steps:**
1. **Option A:** Debug T2-1 evidence validation + adjust prompt to fail triggers as expected
2. **Option B:** Accept conservative baseline + use real data for correction tests (not synthetic)
3. **Option C:** Keep tuned prompt, adjust test expectations for CP1-1/CP4-2

What should we prioritize?
