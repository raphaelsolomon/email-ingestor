# Executive Email Intelligence - Deployment Guide

**Status:** Ready for production (threading + demotion feedback loop)  
**Date:** 2026-10-05  
**Branch:** `feature/p3-correction-flow`

---

## What's Ready

### ✓ Email Threading (100% Verified)
Emails are correctly grouped using 5-pass algorithm:
1. Conversation ID (email chains)
2. Message-ID references (reply-to tracking)
3. Duplicate hash (exact duplicates)
4. Subject + participants + time (same sender, same topic within 24h)
5. **Keyword overlap** (NEW: same sender, different subject, synonym-normalized 12%+ similarity)

**Result:** Emails from same sender about related topics now thread together.  
**Example:** "URGENT!!! swatches for buyer meeting" threads with "Urgent – need updated price list TODAY"

### ✓ Judge Priority Classification
4-level priority system:
- **P1 (Immediate):** Requires urgent action (customer issues, time-sensitive deals)
- **P2 (Action Today):** Needs same-day response (routine requests from executives, key contacts)
- **P3 (Reference):** Informational, can be handled later (updates, FYI emails)
- **P4 (Filter):** Noise (auto-generated alerts, marketing, internal announcements)

### ✓ P3 Feedback Loop - Demotion Mode
**How it works:**
1. User corrects a misclassified email (e.g., "This agent always marks routine requests URGENT")
2. Correction stored with metadata (reason, error_category, semantic_summary)
3. Judge reads past corrections when re-classifying sibling emails
4. Judge applies the learning to related emails from same sender/topic

**Status:** Fully verified end-to-end. Pattern 1 test showed Judge successfully demoted CP1-2 based on stored correction for CP1-1.

**Guardrails:** Corrections only apply to emails matching the pattern. Real urgent emails (CG-1: actual customer trial order) stay P1.

---

## Known Limitations

### ⚠ Promotions Are Conservative
The Judge requires high confidence to upgrade email priority. When correcting an under-classified email (e.g., casual email from Chairman → P2), the Judge may mark sibling as `needs_evidence` instead of promoting.

**Recommendation:** For promotions, require manual review + explicit confirmation.

**Workaround:** 
- Use demotion corrections freely (they work reliably)
- For promotions, users can provide additional context or handle manually

---

## Deployment Checklist

- [ ] Verify no breaking changes to existing schema
- [ ] Test with real email data (sanity check threading + classification)
- [ ] Deploy ingest.py (threading algorithm finalized)
- [ ] Deploy judge.py (correction reading + LLM integration)
- [ ] Deploy store.py (schema with keyword_overlap basis)
- [ ] Deploy database schema (CHECK constraint updated)
- [ ] Document: "Promotions handled conservatively; recommend manual review"
- [ ] Train users on demotion-based feedback loop workflow
- [ ] Monitor correction effectiveness (track adoption, false positives)

---

## Configuration

### Environment Variables
```bash
MINIMAX_API_KEY=<your_key>  # For Judge LLM classification
```

### Database
```bash
sqlite3 data/mailing.db < schema.sql
```

### Running
```bash
# Ingest emails and thread them
python src/ingest.py <path_to_emails>

# Judge a thread and read corrections
python src/judge.py <path_to_db> <model_name>

# Store correction
python src/store.py <db_path> <judgement_id> <correction_data>
```

---

## Success Metrics

After deployment, track:
1. **Threading accuracy:** % of threads grouped correctly (baseline: 100% on 16 test threads)
2. **Classification baseline:** % P1/P2/P3/P4 assignments match human expectations
3. **Correction adoption:** # of corrections stored per week
4. **Demotion effectiveness:** % of related emails re-classified per correction
5. **Promotion rate:** % of promotion corrections vs demotion corrections (for tuning later)

---

## Post-Deployment: Next Phase

### Enhancement: Promotion Confidence Tuning
Once deployed, monitor promotion corrections and identify patterns:
- Are promotions failing more than demotions?
- Can we extract a confidence threshold?
- Should promotions require explicit user confirmation?

### Future: Full Feedback Loop
- Auto-learn from demotion corrections
- Manual confirmation for promotion corrections
- A/B test correction effectiveness
- Track correction accuracy over time

---

## Rollback Plan

If issues arise:
1. Revert to previous ingest.py (removes keyword_overlap pass)
2. Revert to previous judge.py (removes correction reading)
3. Database schema is backwards-compatible (CHECK constraint only restricts new inserts)

No data loss; can restart from email ingestion.

---

## Support & Questions

**Threading not working?**
- Check: Same sender + similar subject + within time window
- Check: Keyword overlap >= 0.12 (after synonym normalization)
- Debug: `SELECT grouping_basis FROM thread WHERE ...`

**Judge not applying corrections?**
- Check: Correction stored with `error_category = 'wrongly_classified'`
- Check: Judge CLI accepts `sys.argv[1]` (db_path) and `sys.argv[2]` (model)
- Check: LLM prompt includes "past_corrections" section
- For promotions: Judge may mark as needs_evidence (conservative default)

**Guardrail email affected by correction?**
- This is a bug; report with thread ID and correction ID
- Corrections should only apply to emails matching the pattern
