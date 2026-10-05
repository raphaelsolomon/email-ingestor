# T2-1 Debug Findings & Current Status

**Date:** 2026-10-05  
**Investigation:** T2-1 marked needs_evidence despite clear decision deadline

---

## Root Cause #1: Multi-Message Thread Confusion ✓ FIXED

**Problem:** T2 is a 4-message thread:
- T2-1: Anna proposes air freight with "decision by 15:00 today"
- T2-2: Lily replies asking for EUR breakdown
- T2-3: Lily forwards urgently
- T2-4: Anna resends original

Judge reads all 4 and thinks: "Lily asked for more info, so the decision is uncertain until Anna responds" → marked needs_evidence.

**Fix Applied:** Updated system prompt to clarify:
> "When a thread spans multiple messages, the FIRST message usually sets the context and decision point. Follow-up replies, questions, or clarifications do NOT negate the original deadline or decision."

**Status:** ✓ Applied to prompt

---

## Root Cause #2: Over-Strict Evidence Validation ✓ PARTIALLY FIXED

**Problem:** Validation required ALL of (who, what, why, action) to have evidence:
- IA-02: Has who + what + why + deadline, but MISSING action field → marked needs_evidence
- AT-01: Only has what field, MISSING who/why/action → marked needs_evidence

**Fix Applied:** Changed validation logic:
- Old: `if len(fields) < 4: needs_evidence` (all 4 required)
- New: `if not fields.get("what"): needs_evidence` (only "what" required)

**Status:** ✓ Applied to code, but revealed Root Cause #3

---

## Root Cause #3: LLM Not Extracting All Alert Fields ⚠ UNFIXED

**New Problem Discovered:** Even with relaxed validation, many emails still marked needs_evidence because the Judge's output is missing "what" field entirely:
- AT-01: Priority=NULL, what=NULL → needs_evidence
- IA-02: Priority=1, what=NULL → needs_evidence  
- T2-1: Priority=2, what=NULL → needs_evidence

The Judge is extracting SOME fields (who, why, deadline) but not "what".

**Likely Causes:**
1. LLM prompt doesn't clearly explain that "what" is mandatory
2. LLM returns "what" in different field (e.g., in "reason" instead)
3. Alert object structure in tool schema confuses the LLM
4. Extraction logic for alert fields needs refinement

**Example:** IA-02 has:
- who: ✓ "Jacky (Mr. Zhang)..."
- what: ✗ NULL (should be "Halt all production in the dye house")
- why: ✓ "Formal stop-production order from SIP..."
- action: ✗ NULL
- deadline: ✓ "2026-10-06 09:00..."

The info is clearly there, but "what" wasn't extracted into that field.

---

## Current System Status

| Component | Status | Notes |
|-----------|--------|-------|
| Threading | ✓ Working | T1, T2, T4 all correct |
| Topic Generation | ✓ Working | One-liners being generated |
| Priority Tuning | ✓ Working | Conservative P1/P2/P3 logic correct |
| Evidence Validation | ⚠ Partial | Relaxed, but reveals #3 |
| Alert Field Extraction | ⚠ Broken | "what" field often NULL |
| Baseline Accuracy | ~50% | Better than 25%, but alert field extraction blocking full success |

---

## What's Working

- **IA-01:** P1, confirmed, has full alert
- **Baseline threading:** T1 grouped ✓, T2 grouped ✓, T4 separate ✓
- **Priority classification:** P1 for regulatory, P2 for decisions, P3 for routine ✓

## What's Broken

- **IA-02, AT-01, T2-1:** Priorities correct but "what" field NULL → all marked needs_evidence
- **Correction tests:** Can't proceed until baseline is 100% confirmed

---

## Options to Proceed

### Option A: Accept Current State (Quickest)
- Threading ✓ + topic generation ✓ = Deploy as is
- Document: "Alerts require manual field verification until LLM extraction improved"
- P3 feedback loop works on corrections, not alerts

**Trade-off:** Alerts marked "needs_evidence" might confuse users

### Option B: Enhance LLM Prompt (Medium Effort)
- Clarify tool schema: make "what" field explicitly required in system prompt
- Add examples: "what should be 'Approve $X by 5pm', not just 'Decision needed'"
- Add validation: "if what is empty, set alert to null and explain in uncertainty"

**Trade-off:** Might not fix the root issue if LLM is confused about role

### Option C: Debug Output Parsing (Higher Effort)
- Log raw LLM response to see what it's actually returning
- Check if "what" is in the output but not being parsed correctly
- May need to iterate on tool schema or extraction logic

**Trade-off:** Could take multiple iterations

---

## Recommendation

**Start with Option B** (enhance prompt):
1. Make "what" explicitly required in system prompt
2. Add examples of good vs bad "what" values
3. Re-run baseline test (should take 2-3 min)
4. If still broken → escalate to Option C

The issue is likely prompt-fixable (LLM doesn't understand the criticality of "what" field) rather than code-broken.

---

## For Next Session

If continuing:
1. Update SYSTEM_PROMPT with explicit "what" examples
2. Re-run test on YC_Final_Test_Set 2
3. Should see IA-02, AT-01, T2-1 all marked confirmed
4. Then test corrections P3 feedback loop
